"""Trimmed ffprobe outputs used by the media analysis tests."""

DUAL_AUDIO_MKV = {
    "streams": [
        {"index": 0, "codec_name": "h264", "profile": "High", "codec_type": "video",
         "width": 1920, "height": 1080, "level": 40, "disposition": {"attached_pic": 0}},
        {"index": 1, "codec_name": "eac3", "codec_type": "audio", "channels": 6,
         "tags": {"language": "por", "title": "Portuguese (Brazil)"}},
        {"index": 2, "codec_name": "eac3", "codec_type": "audio", "channels": 6,
         "tags": {"language": "eng", "title": "English (United States)"}},
        {"index": 3, "codec_name": "subrip", "codec_type": "subtitle",
         "tags": {"language": "por", "title": "Portuguese (Brazil) [Forced]"}},
        {"index": 4, "codec_name": "subrip", "codec_type": "subtitle",
         "tags": {"language": "eng", "title": "English (United States) [SDH]"}},
    ],
    "format": {"format_name": "matroska,webm", "duration": "1332.416000", "size": "1717986918"},
}  # fmt: skip

MP3_WITH_COVER = {
    "streams": [
        {"index": 0, "codec_name": "mp3", "codec_type": "audio", "channels": 2},
        {"index": 1, "codec_name": "mjpeg", "codec_type": "video", "width": 500, "height": 500,
         "disposition": {"attached_pic": 1}},
    ],
    "format": {"format_name": "mp3", "duration": "74.5", "size": "1200000"},
}  # fmt: skip

VIDEO_WITHOUT_AUDIO = {
    "streams": [
        {"index": 0, "codec_name": "hevc", "codec_type": "video", "width": 3840, "height": 2160,
         "level": 153, "profile": "Main 10"},
    ],
    "format": {"format_name": "matroska,webm", "duration": "10", "size": "1000"},
}  # fmt: skip
