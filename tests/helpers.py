"""Helpers shared by the pipeline tests."""

import wave
from pathlib import Path

SAMPLE_RATE = 16000
#: Length of the audio the generic ffmpeg fakes pretend to extract: a single Bloco.
FAKE_AUDIO_SECONDS = 3


def write_silent_wav(path: str | Path, seconds: float) -> None:
    """Write a mono 16 kHz 16-bit silent WAV, like the one extract_audio produces.

    Args:
        path: Output file.
        seconds: Duration.
    """
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"\x00\x00" * int(seconds * SAMPLE_RATE))
