"""Análise da Mídia: read a media file with ffprobe and describe it for the modal.

The browser decides what it can play (canPlayType); this module only provides the
MIME strings it needs, plus human labels in pt-BR.
"""

import json
import subprocess
from pathlib import PurePath
from typing import Any

from loguru import logger

PROBE_TIMEOUT_SECONDS = 60

#: Containers a browser opens directly in a media element.
BROWSER_CONTAINERS = frozenset({"mp4", "webm", "mp3", "m4a", "wav", "ogg"})

VIDEO_LABELS = {
    "h264": "H.264",
    "hevc": "HEVC (H.265)",
    "av1": "AV1",
    "vp9": "VP9",
    "vp8": "VP8",
    "mpeg4": "MPEG-4",
}
AUDIO_LABELS = {
    "aac": "AAC",
    "mp3": "MP3",
    "eac3": "E-AC-3",
    "ac3": "AC-3",
    "opus": "Opus",
    "vorbis": "Vorbis",
    "flac": "FLAC",
    "dts": "DTS",
    "truehd": "Dolby TrueHD",
    "alac": "ALAC",
}
AUDIO_MIMES = {
    "aac": 'audio/mp4; codecs="mp4a.40.2"',
    "mp3": "audio/mpeg",
    "eac3": 'audio/mp4; codecs="ec-3"',
    "ac3": 'audio/mp4; codecs="ac-3"',
    "opus": 'audio/webm; codecs="opus"',
    "vorbis": 'audio/webm; codecs="vorbis"',
    "flac": "audio/flac",
    "dts": 'audio/mp4; codecs="dtsc"',
    "truehd": 'audio/mp4; codecs="mlpa"',
    "alac": 'audio/mp4; codecs="alac"',
}
H264_PROFILES = {"Baseline": "42", "Constrained Baseline": "42", "Main": "4d", "High": "64"}
CHANNEL_LABELS = {1: "Mono", 2: "Estéreo", 6: "5.1", 8: "7.1"}
DEFAULT_H264_LEVEL = 40
DEFAULT_HEVC_LEVEL = 120


class AnalysisError(Exception):
    """The file cannot be used. The message is pt-BR and shown to the person."""


def analyze(path: str) -> dict[str, Any]:
    """Run ffprobe on ``path`` and describe the media.

    Args:
        path: Media file on disk.

    Returns:
        The analysis (see ``parse_probe``).

    Raises:
        AnalysisError: If ffprobe cannot read the file or it has no audio track.
    """
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]  # fmt: skip
    try:
        # Fixed ffprobe argv, no shell; the path comes from our own storage.
        probe = subprocess.run(  # noqa: S603
            cmd, check=True, capture_output=True, text=True, timeout=PROBE_TIMEOUT_SECONDS
        )
        data = json.loads(probe.stdout)
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ) as error:
        logger.warning(f"ffprobe could not read {path}: {error}")
        raise AnalysisError("Não foi possível ler o arquivo. Ele pode estar corrompido.") from error
    return parse_probe(data, extension=PurePath(path).suffix.lstrip("."))


def parse_probe(data: dict[str, Any], *, extension: str) -> dict[str, Any]:
    """Turn ffprobe JSON into the analysis shown in the modal.

    Args:
        data: ffprobe output with ``streams`` and ``format``.
        extension: File extension, used for the container label.

    Returns:
        ``format_label``, ``browser_container``, ``size_bytes``, ``duration_seconds``,
        ``video`` (or None), ``audio_tracks`` and ``subtitles``.

    Raises:
        AnalysisError: If there is no audio track to transcribe.
    """
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    audio = [_audio_track(s) for s in streams if s.get("codec_type") == "audio"]
    if not audio:
        raise AnalysisError("Este arquivo não tem faixa de áudio para transcrever.")
    videos = [
        s
        for s in streams
        if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
    ]
    ext = extension.lower()
    duration = fmt.get("duration")
    return {
        "format_label": ext.upper(),
        "browser_container": ext in BROWSER_CONTAINERS,
        "size_bytes": int(fmt.get("size", 0)),
        "duration_seconds": float(duration) if duration else None,
        "video": _video_info(videos[0]) if videos else None,
        "audio_tracks": audio,
        "subtitles": [
            {"language": _tag(s, "language"), "title": _tag(s, "title")}
            for s in streams
            if s.get("codec_type") == "subtitle"
        ],
    }


def _tag(stream: dict[str, Any], name: str) -> str | None:
    """A stream tag, or None when missing or undefined."""
    value = stream.get("tags", {}).get(name)
    return None if value in (None, "", "und") else value


def _video_info(stream: dict[str, Any]) -> dict[str, Any]:
    """Describe the main video stream."""
    codec = stream.get("codec_name", "")
    return {
        "codec_label": VIDEO_LABELS.get(codec, codec.upper()),
        "width": stream.get("width", 0),
        "height": stream.get("height", 0),
        "mime": video_mime(stream),
    }


def _audio_track(stream: dict[str, Any]) -> dict[str, Any]:
    """Describe one audio stream."""
    codec = stream.get("codec_name", "")
    channels = int(stream.get("channels", 0))
    return {
        "index": stream["index"],
        "language": _tag(stream, "language"),
        "title": _tag(stream, "title"),
        "codec_label": "PCM"
        if codec.startswith("pcm_")
        else AUDIO_LABELS.get(codec, codec.upper()),
        "channels": channels,
        "channel_label": channel_label(channels),
        "mime": "audio/wav"
        if codec.startswith("pcm_")
        else AUDIO_MIMES.get(codec, f"audio/x-{codec}"),
    }


def video_mime(stream: dict[str, Any]) -> str:
    """MIME type with RFC 6381 codec string for ``canPlayType``.

    Args:
        stream: An ffprobe video stream.

    Returns:
        e.g. ``video/mp4; codecs="avc1.640028"``.
    """
    codec = stream.get("codec_name", "")
    if codec == "h264":
        profile = H264_PROFILES.get(stream.get("profile", ""), "64")
        level = int(stream.get("level") or DEFAULT_H264_LEVEL)
        return f'video/mp4; codecs="avc1.{profile}00{level:02x}"'
    if codec == "hevc":
        level = int(stream.get("level") or DEFAULT_HEVC_LEVEL)
        return f'video/mp4; codecs="hvc1.1.6.L{level}.B0"'
    if codec == "av1":
        return 'video/mp4; codecs="av01.0.08M.08"'
    if codec in {"vp9", "vp8"}:
        return f'video/webm; codecs="{codec}"'
    if codec == "mpeg4":
        return 'video/mp4; codecs="mp4v.20.9"'
    return f"video/x-{codec}"


def channel_label(channels: int) -> str:
    """pt-BR label for a channel count (e.g. 2 → "Estéreo", 6 → "5.1")."""
    return CHANNEL_LABELS.get(channels, f"{channels} canais")
