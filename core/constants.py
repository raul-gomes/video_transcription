"""Domain constants shared by models, services, the API and the pipeline."""

from dataclasses import dataclass

VIDEO_EXTENSIONS = frozenset({"mp4", "mkv", "mov", "webm"})
AUDIO_EXTENSIONS = frozenset({"mp3", "wav", "m4a", "ogg"})
ACCEPTED_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

AUTO_LANGUAGE = "auto"
DEFAULT_LANGUAGE = "pt"


@dataclass(frozen=True)
class Language:
    """A speech language offered on the upload screen."""

    code: str
    label: str


LANGUAGES = (
    Language("pt", "Português"),
    Language("en", "Inglês"),
    Language("es", "Espanhol"),
    Language(AUTO_LANGUAGE, "Detectar automaticamente"),
)
LANGUAGE_CODES = frozenset(language.code for language in LANGUAGES)


@dataclass(frozen=True)
class WhisperModel:
    """A Whisper model size offered on the upload screen."""

    name: str
    label: str
    hint: str


WHISPER_MODELS = (
    WhisperModel("tiny", "Tiny", "Muito rápido, menos preciso"),
    WhisperModel("base", "Base", "Rápido"),
    WhisperModel("small", "Small", "Equilíbrio (recomendado)"),
    WhisperModel("medium", "Medium", "Mais preciso; lento em CPU, ~5 GB de memória de vídeo"),
    WhisperModel("large", "Large", "O mais preciso; precisa de ~10 GB de memória de vídeo"),
)
WHISPER_MODEL_NAMES = frozenset(model.name for model in WHISPER_MODELS)

DEVICE_AUTO = "auto"
DEVICE_CPU = "cpu"
DEVICE_GPU = "gpu"
DEVICES = frozenset({DEVICE_AUTO, DEVICE_CPU, DEVICE_GPU})

BYTES_PER_MB = 1024 * 1024
