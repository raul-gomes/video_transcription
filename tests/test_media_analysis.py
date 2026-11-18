"""Tests for the Análise da Mídia (ffprobe parsing and the ffprobe call)."""

import json
import subprocess
from unittest.mock import MagicMock

import pytest

from core import media_analysis
from core.media_analysis import AnalysisError, analyze, parse_probe
from tests.fixtures.probes import DUAL_AUDIO_MKV, MP3_WITH_COVER, VIDEO_WITHOUT_AUDIO


def test_dual_audio_mkv() -> None:
    result = parse_probe(DUAL_AUDIO_MKV, extension="mkv")

    assert result["format_label"] == "MKV"
    assert result["browser_container"] is False
    assert result["size_bytes"] == 1717986918
    assert result["duration_seconds"] == pytest.approx(1332.416)
    assert result["video"] == {
        "codec_label": "H.264",
        "width": 1920,
        "height": 1080,
        "mime": 'video/mp4; codecs="avc1.640028"',
    }
    assert result["audio_tracks"] == [
        {
            "index": 1,
            "language": "por",
            "title": "Portuguese (Brazil)",
            "codec_label": "E-AC-3",
            "channels": 6,
            "channel_label": "5.1",
            "mime": 'audio/mp4; codecs="ec-3"',
        },
        {
            "index": 2,
            "language": "eng",
            "title": "English (United States)",
            "codec_label": "E-AC-3",
            "channels": 6,
            "channel_label": "5.1",
            "mime": 'audio/mp4; codecs="ec-3"',
        },
    ]
    assert result["subtitles"] == [
        {"language": "por", "title": "Portuguese (Brazil) [Forced]"},
        {"language": "eng", "title": "English (United States) [SDH]"},
    ]


def test_cover_art_is_not_video() -> None:
    result = parse_probe(MP3_WITH_COVER, extension="mp3")

    assert result["video"] is None
    assert result["browser_container"] is True
    assert result["audio_tracks"][0]["channel_label"] == "Estéreo"
    assert result["audio_tracks"][0]["mime"] == "audio/mpeg"


def test_media_without_audio_is_refused() -> None:
    with pytest.raises(AnalysisError, match="faixa de áudio"):
        parse_probe(VIDEO_WITHOUT_AUDIO, extension="mkv")


@pytest.mark.parametrize(
    ("stream", "mime"),
    [
        ({"codec_name": "hevc", "level": 153}, 'video/mp4; codecs="hvc1.1.6.L153.B0"'),
        ({"codec_name": "h264", "profile": "Main", "level": 31}, 'video/mp4; codecs="avc1.4d001f"'),
        ({"codec_name": "vp9"}, 'video/webm; codecs="vp9"'),
        ({"codec_name": "weird"}, "video/x-weird"),
    ],
)
def test_video_mime(stream: dict, mime: str) -> None:
    assert media_analysis.video_mime(stream) == mime


@pytest.mark.parametrize(("channels", "label"), [(1, "Mono"), (8, "7.1"), (4, "4 canais")])
def test_channel_labels(channels: int, label: str) -> None:
    assert media_analysis.channel_label(channels) == label


def test_analyze_runs_ffprobe(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = MagicMock(
        return_value=subprocess.CompletedProcess([], 0, stdout=json.dumps(DUAL_AUDIO_MKV))
    )
    monkeypatch.setattr(media_analysis.subprocess, "run", runner)

    result = analyze("/data/media/videos/x.mkv")

    assert result["format_label"] == "MKV"
    argv = runner.call_args.args[0]
    assert argv[0] == "ffprobe" and argv[-1] == "/data/media/videos/x.mkv"


def test_unreadable_file_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    error = subprocess.CalledProcessError(1, ["ffprobe"], stderr="Invalid data")
    monkeypatch.setattr(media_analysis.subprocess, "run", MagicMock(side_effect=error))

    with pytest.raises(AnalysisError, match="ler o arquivo"):
        analyze("/x.mkv")
