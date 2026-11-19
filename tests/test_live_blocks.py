"""Live transcription by Blocos (ADR 0003): Whisper and ffmpeg are fakes."""

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from django.core.files.base import ContentFile
from pytest_django.fixtures import Settings

from core import utils
from core.models import TranscriptionJob
from core.utils import VideoProcessor, accept_segments, plan_blocks
from tests.helpers import write_silent_wav

MEDIA_SECONDS = 65  # three Blocos: 0-30, 28-58, 56-65


class TestPlanBlocks:
    """30 s Blocos, each repeating the last 2 s of the previous one."""

    @pytest.mark.parametrize(
        ("duration", "expected"),
        [
            (10, [(0, 10)]),
            (30, [(0, 30)]),
            (31, [(0, 30), (28, 31)]),
            (65, [(0, 30), (28, 58), (56, 65)]),
        ],
    )
    def test_blocks(self, duration: float, expected: list[tuple[float, float]]) -> None:
        assert plan_blocks(duration) == expected


class TestAcceptSegments:
    """Segments are moved to media time; only those after the Fronteira are kept."""

    def test_shifts_by_block_start(self) -> None:
        raw = [{"start": 1.0, "end": 2.5, "text": " Oi."}]
        assert accept_segments(raw, offset=28, frontier=0) == [
            {"start": 29.0, "end": 30.5, "text": " Oi."}
        ]

    def test_drops_segments_starting_before_the_frontier(self) -> None:
        raw = [
            {"start": 0.5, "end": 1.8, "text": " repetido"},
            {"start": 2.2, "end": 4.0, "text": " novo"},
        ]
        accepted = accept_segments(raw, offset=28, frontier=29.9)
        assert [segment["text"] for segment in accepted] == [" novo"]

    def test_keeps_whisper_fields(self) -> None:
        raw = [{"start": 0.0, "end": 1.0, "text": " a", "avg_logprob": -0.2}]
        assert accept_segments(raw, offset=0, frontier=0)[0]["avg_logprob"] == -0.2


@pytest.fixture
def media_root(settings: Settings, tmp_path: Path) -> Path:
    """Point MEDIA_ROOT at a per-test directory."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake ffmpeg: the extracted audio is a real 65 s silent WAV."""

    def run(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[bytes]:
        output = cmd[-1]
        if output.endswith(".wav"):
            write_silent_wav(output, MEDIA_SECONDS)
        else:
            Path(output).write_bytes(b"fake-output")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(utils.subprocess, "run", MagicMock(side_effect=run))


def make_job(language: str = "auto") -> TranscriptionJob:
    """A queued video job."""
    job = TranscriptionJob(status="queued", language=language)
    job.media_file.save("aula.mp4", ContentFile(b"fake-video"), save=False)
    job.save()
    return job


Responder = Callable[[int, dict[str, Any]], dict[str, Any]]


@pytest.fixture
def whisper(monkeypatch: pytest.MonkeyPatch) -> Callable[[Responder], MagicMock]:
    """Install a fake model whose answer for call N comes from ``respond(N, kwargs)``."""

    def install(respond: Responder) -> MagicMock:
        model = MagicMock()
        calls = {"n": 0}

        def transcribe(audio: Any, **kwargs: Any) -> dict[str, Any]:
            calls["n"] += 1
            return respond(calls["n"], kwargs)

        model.transcribe.side_effect = transcribe
        monkeypatch.setattr(utils.whisper, "load_model", MagicMock(return_value=model))
        return model

    return install


def three_blocks(call: int, _: dict[str, Any]) -> dict[str, Any]:
    """Block 1 ends on a phrase crossing the cut; block 2 repeats it in its overlap."""
    answers = {
        1: [
            {"start": 0.0, "end": 10.0, "text": " Primeira frase."},
            {"start": 25.0, "end": 29.5, "text": " Frase no corte."},
        ],
        2: [
            {"start": 0.5, "end": 1.5, "text": " no corte."},  # 28.5 s: already covered
            {"start": 3.0, "end": 8.0, "text": " Segunda parte."},  # 31 s
        ],
        3: [{"start": 4.0, "end": 6.0, "text": " Fim."}],  # 60 s
    }
    return {"language": "en", "segments": answers[call]}


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root", "ffmpeg")
class TestBlockPipeline:
    """The pipeline transcribes Bloco by Bloco and publishes as it goes."""

    def test_stores_segments_in_media_time_without_duplicates(self, whisper: Any) -> None:
        whisper(three_blocks)
        job = make_job()

        VideoProcessor(job).process()
        job.refresh_from_db()

        assert job.status == "completed"
        assert [(s.start_time, s.text) for s in job.segments.order_by("start_time")] == [
            (0.0, " Primeira frase."),
            (25.0, " Frase no corte."),
            (31.0, " Segunda parte."),
            (60.0, " Fim."),
        ]

    def test_each_block_gets_one_slice_of_audio(self, whisper: Any) -> None:
        model = whisper(three_blocks)

        VideoProcessor(make_job()).process()

        lengths = [len(call.args[0]) / 16000 for call in model.transcribe.call_args_list]
        assert lengths == [30, 30, 9]

    def test_passes_the_previous_text_as_context(self, whisper: Any) -> None:
        model = whisper(three_blocks)

        VideoProcessor(make_job()).process()

        prompts = [call.kwargs.get("initial_prompt") for call in model.transcribe.call_args_list]
        assert prompts[0] is None
        assert prompts[1] == "Primeira frase. Frase no corte."
        assert prompts[2].endswith("Segunda parte.")

    def test_context_is_capped(self, whisper: Any) -> None:
        long_text = " " + "palavra " * 100

        def respond(call: int, _: dict[str, Any]) -> dict[str, Any]:
            if call == 1:
                return {"language": "pt", "segments": [{"start": 0, "end": 20, "text": long_text}]}
            return {"language": "pt", "segments": []}

        model = whisper(respond)
        VideoProcessor(make_job()).process()

        prompt = model.transcribe.call_args_list[1].kwargs["initial_prompt"]
        assert len(prompt) <= utils.CONTEXT_CHARS
        assert long_text.strip().endswith(prompt)

    def test_auto_language_is_detected_once_and_kept(self, whisper: Any) -> None:
        def respond(call: int, _: dict[str, Any]) -> dict[str, Any]:
            if call == 1:  # silent intro: Whisper guesses, but there is no speech
                return {"language": "ja", "segments": []}
            return {"language": "en", "segments": [{"start": 1, "end": 2, "text": " Hi."}]}

        model = whisper(respond)
        job = make_job("auto")

        VideoProcessor(job).process()
        job.refresh_from_db()

        languages = [call.kwargs["language"] for call in model.transcribe.call_args_list]
        assert languages == [None, None, "en"]
        assert job.detected_language == "en"
        assert job.language == "auto"

    def test_chosen_language_is_used_for_every_block(self, whisper: Any) -> None:
        model = whisper(three_blocks)
        job = make_job("pt")

        VideoProcessor(job).process()
        job.refresh_from_db()

        assert {call.kwargs["language"] for call in model.transcribe.call_args_list} == {"pt"}
        assert job.detected_language == ""

    def test_publishes_progress_and_partial_subtitles_per_block(self, whisper: Any) -> None:
        job = make_job()
        seen: list[tuple[str, int, str]] = []

        def respond(call: int, kwargs: dict[str, Any]) -> dict[str, Any]:
            current = TranscriptionJob.objects.get(pk=job.pk)
            srt = current.srt_file.read().decode() if current.srt_file else ""
            seen.append((current.current_step, current.progress_percentage, srt))
            return three_blocks(call, kwargs)

        whisper(respond)
        VideoProcessor(job).process()

        steps = [step for step, _, _ in seen]
        assert steps == [
            "Transcrevendo bloco 1 de 3",
            "Transcrevendo bloco 2 de 3",
            "Transcrevendo bloco 3 de 3",
        ]
        progress = [percentage for _, percentage, _ in seen]
        assert progress == sorted(progress)
        assert progress[0] >= utils.PROGRESS_TRANSCRIBE
        assert progress[-1] < utils.PROGRESS_GENERATE
        assert seen[0][2] == ""
        assert "Frase no corte." in seen[1][2]
        assert "Segunda parte." in seen[2][2]

    def test_partial_files_keep_a_stable_name(self, whisper: Any) -> None:
        job = make_job()
        names: list[str] = []

        def respond(call: int, kwargs: dict[str, Any]) -> dict[str, Any]:
            current = TranscriptionJob.objects.get(pk=job.pk)
            names.append(current.vtt_file.name)
            return three_blocks(call, kwargs)

        whisper(respond)
        VideoProcessor(job).process()
        job.refresh_from_db()

        assert names[1] == names[2] == job.vtt_file.name

    def test_failure_mid_job_keeps_what_was_transcribed(self, whisper: Any) -> None:
        def respond(call: int, kwargs: dict[str, Any]) -> dict[str, Any]:
            if call == 2:
                raise RuntimeError("boom")
            return three_blocks(call, kwargs)

        whisper(respond)
        job = make_job()

        VideoProcessor(job).process()
        job.refresh_from_db()

        assert job.status == "failed"
        assert [s.text for s in job.segments.order_by("start_time")] == [
            " Primeira frase.",
            " Frase no corte.",
        ]
        assert "Frase no corte." in job.srt_file.read().decode()


@pytest.mark.django_db
@pytest.mark.usefixtures("media_root")
class TestDetectedLanguageApi:
    """The detected language reaches the page and is reset on Reprocessar."""

    def test_job_payload_has_detected_language(self) -> None:
        from core.serializers import JobSerializer

        job = make_job("auto")
        assert JobSerializer(job).data["detected_language"] is None
        job.detected_language = "en"
        assert JobSerializer(job).data["detected_language"] == "en"

    def test_retry_clears_detected_language(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from core import services

        monkeypatch.setattr(services, "_enqueue", lambda job: None)
        job = make_job("auto")
        job.status = "failed"
        job.detected_language = "en"
        job.save()

        services.retry_job(job)
        job.refresh_from_db()

        assert job.detected_language == ""
