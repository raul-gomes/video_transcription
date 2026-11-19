/**
 * API contract used by the client (api.js). Field names match the JSON the
 * backend returns (core/serializers.py).
 */

/**
 * @typedef {'awaiting_decision'|'queued'|'preparing_preview'|'downloading_model'|'extracting'|'transcribing'|'generating'
 *   |'completed'|'failed'|'cancelled'|'interrupted'} JobStatus
 */

/**
 * @typedef {Object} JobFiles
 * @property {string} media        Original uploaded media (always present).
 * @property {string|null} preview  Browser Prévia, when the person asked for one.
 * @property {string|null} video  Subtitled video (null for audio media).
 * @property {string|null} srt   Partial while the job is running (rewritten after each Bloco).
 * @property {string|null} vtt   Partial while the job is running (rewritten after each Bloco).
 * @property {string|null} txt
 * @property {string|null} json
 */

/**
 * @typedef {Object} Job
 * @property {string} id
 * @property {string} filename         Original media file name.
 * @property {'video'|'audio'} media_kind
 * @property {JobStatus} status
 * @property {number} progress         0..100.
 * @property {string} step_label       Current step, already in pt-BR.
 * @property {string|null} error       Error message when status is failed.
 * @property {string} language         Whisper language code, or "auto".
 * @property {string|null} detected_language  Language Whisper found in the first Bloco with speech (auto only).
 * @property {string} model            Whisper model size.
 * @property {'auto'|'cpu'|'gpu'} device
 * @property {string} created_at       ISO 8601.
 * @property {number|null} duration_seconds
 * @property {JobFiles} files
 * @property {MediaAnalysis|null} analysis  Filled at upload (Análise da Mídia).
 */

/**
 * @typedef {Object} VideoInfo
 * @property {string} codec_label   e.g. "H.264", "HEVC (H.265)".
 * @property {number} width
 * @property {number} height
 * @property {string} mime          For canPlayType, e.g. 'video/mp4; codecs="avc1.640028"'.
 */

/**
 * @typedef {Object} AudioTrack
 * @property {number} index         Stream index inside the file.
 * @property {string|null} language ISO 639-2 tag from the file (e.g. "por"), if any.
 * @property {string|null} title    Track title from the file, if any.
 * @property {string} codec_label   e.g. "E-AC-3", "AAC".
 * @property {number} channels
 * @property {string} channel_label e.g. "5.1", "Estéreo".
 * @property {string} mime          For canPlayType, e.g. 'audio/mp4; codecs="ec-3"'.
 */

/**
 * @typedef {Object} SubtitleTrack
 * @property {string|null} language
 * @property {string|null} title
 */

/**
 * @typedef {Object} MediaAnalysis
 * @property {string} format_label        e.g. "MKV", "MP4".
 * @property {boolean} browser_container  Whether browsers open this container directly.
 * @property {number} size_bytes
 * @property {number|null} duration_seconds
 * @property {VideoInfo|null} video       Null for audio-only media.
 * @property {AudioTrack[]} audio_tracks  At least one (files without audio are refused).
 * @property {SubtitleTrack[]} subtitles  Embedded subtitles (information only).
 */

/**
 * @typedef {Object} Decision
 * @property {number} audio_track    AudioTrack.index to transcribe.
 * @property {string} language
 * @property {string} model
 * @property {'auto'|'cpu'|'gpu'} device
 * @property {boolean} preview       Build the browser Prévia.
 * @property {boolean} convert_video Also re-encode the picture in the Prévia (slow).
 */

/**
 * @typedef {Object} Segment
 * @property {number} start  Seconds from the start of the media.
 * @property {number} end
 * @property {string} text
 */

/**
 * @typedef {Object} Options
 * @property {{code: string, label: string}[]} languages
 * @property {{name: string, label: string, hint: string}[]} models
 * @property {string} default_language
 * @property {string} default_model
 * @property {boolean} gpu_available   Detected by the worker.
 * @property {number} max_upload_mb
 * @property {string[]} accepted_extensions  Lowercase, without the dot.
 */

/** pt-BR label and badge style per status. */
export const STATUS = {
  awaiting_decision: { label: 'Aguardando sua decisão', tone: 'warning' },
  queued: { label: 'Na fila', tone: 'info' },
  preparing_preview: { label: 'Preparando prévia', tone: 'info' },
  downloading_model: { label: 'Baixando modelo…', tone: 'info' },
  extracting: { label: 'Extraindo áudio', tone: 'info' },
  transcribing: { label: 'Transcrevendo', tone: 'info' },
  generating: { label: 'Gerando legendas', tone: 'info' },
  completed: { label: 'Concluído', tone: 'success' },
  failed: { label: 'Falhou', tone: 'error' },
  cancelled: { label: 'Cancelado', tone: 'warning' },
  interrupted: { label: 'Interrompido', tone: 'warning' },
};

/** ISO 639-2 tags in media files mapped to the app's language codes. */
export const TRACK_LANGUAGE_TO_CODE = { por: 'pt', eng: 'en', spa: 'es' };

/** Statuses where the job is still moving and can be cancelled (files may be partial). */
export const ACTIVE_STATUSES = new Set([
  'queued', 'preparing_preview', 'downloading_model', 'extracting', 'transcribing', 'generating',
]);

/** Downloads that exist (partially) before the job ends. */
export const PARTIAL_FILES = new Set(['srt', 'vtt']);

/** The player resumes once the transcript is this many seconds ahead of it. */
export const RESUME_AHEAD_SECONDS = 3;

/** Statuses that can be sent back to the queue. */
export const RETRYABLE_STATUSES = new Set(['failed', 'cancelled', 'interrupted']);

export const DEVICE_LABELS = { auto: 'Automático', cpu: 'CPU', gpu: 'GPU' };

/** How often the page asks the backend for job updates. */
export const POLL_INTERVAL_MS = 5000;
