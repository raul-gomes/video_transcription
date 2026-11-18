/**
 * API contract used by the client (api.js). Field names match the JSON the
 * backend returns (core/serializers.py).
 */

/**
 * @typedef {'queued'|'downloading_model'|'extracting'|'transcribing'|'generating'
 *   |'completed'|'failed'|'cancelled'|'interrupted'} JobStatus
 */

/**
 * @typedef {Object} JobFiles
 * @property {string} media        Original uploaded media (always present).
 * @property {string|null} video  Subtitled video (null for audio media).
 * @property {string|null} srt
 * @property {string|null} vtt
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
 * @property {string} model            Whisper model size.
 * @property {'auto'|'cpu'|'gpu'} device
 * @property {string} created_at       ISO 8601.
 * @property {number|null} duration_seconds
 * @property {JobFiles} files
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
  queued: { label: 'Na fila', tone: 'info' },
  downloading_model: { label: 'Baixando modelo…', tone: 'info' },
  extracting: { label: 'Extraindo áudio', tone: 'info' },
  transcribing: { label: 'Transcrevendo', tone: 'info' },
  generating: { label: 'Gerando legendas', tone: 'info' },
  completed: { label: 'Concluído', tone: 'success' },
  failed: { label: 'Falhou', tone: 'error' },
  cancelled: { label: 'Cancelado', tone: 'warning' },
  interrupted: { label: 'Interrompido', tone: 'warning' },
};

/** Statuses where the job is still moving and can be cancelled. */
export const ACTIVE_STATUSES = new Set([
  'queued', 'downloading_model', 'extracting', 'transcribing', 'generating',
]);

/** Statuses that can be sent back to the queue. */
export const RETRYABLE_STATUSES = new Set(['failed', 'cancelled', 'interrupted']);

export const DEVICE_LABELS = { auto: 'Automático', cpu: 'CPU', gpu: 'GPU' };

/** How often the page asks the backend for job updates. */
export const POLL_INTERVAL_MS = 5000;
