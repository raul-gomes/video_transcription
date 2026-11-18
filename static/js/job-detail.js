/**
 * Expanded area of a job card: media player plus the transcript, which grows
 * while the job runs. Created once per opening so polling never restarts playback.
 */

import { ACTIVE_STATUSES } from './contract.js';
import { el, formatDuration } from './dom.js';

/** @typedef {import('./contract.js').Job} Job */
/** @typedef {import('./contract.js').Segment} Segment */

/**
 * @typedef {Object} JobDetail
 * @property {HTMLElement} element
 * @property {(job: Job) => Promise<void>} update  Pull new segments and refresh subtitles.
 * @property {() => void} destroy                   Stop playback before removal.
 */

/**
 * Build the detail area for a job.
 * @param {Job} job
 * @param {(id: string, after: number) => Promise<Segment[]>} loadSegments
 * @returns {JobDetail}
 */
export function createDetail(job, loadSegments) {
  const isVideo = job.media_kind === 'video';
  const player = /** @type {HTMLMediaElement} */ (el(isVideo ? 'video' : 'audio', {
    class: 'job-detail__player', controls: true, preload: 'metadata', src: job.files.media,
  }));
  const list = el('ol', { class: 'transcript', 'aria-label': 'Transcrição' });
  const status = el('p', { class: 'transcript__status' });
  /** @type {{segment: Segment, item: HTMLElement}[]} */
  const rows = [];
  let lastStart = -1;
  let trackSrc = null;

  const element = el('div', { class: 'job-detail' }, [
    el('div', { class: 'job-detail__media' }, [player]),
    el('div', { class: 'job-detail__text' }, [
      el('h4', { class: 'job-detail__title', text: 'Transcrição' }),
      list,
      status,
    ]),
  ]);

  player.addEventListener('timeupdate', () => {
    const now = player.currentTime;
    for (const { segment, item } of rows) {
      item.classList.toggle('is-current', now >= segment.start && now < segment.end);
    }
  });

  /** @param {Segment} segment */
  const addRow = (segment) => {
    const item = el('li', { class: 'transcript__item' }, [
      el('button', {
        class: 'transcript__time', type: 'button', text: formatDuration(segment.start),
        'aria-label': `Ir para ${formatDuration(segment.start)}`,
        onClick: () => { player.currentTime = segment.start; player.play().catch(() => {}); },
      }),
      el('span', { text: segment.text.trim() }),
    ]);
    rows.push({ segment, item });
    list.append(item);
    lastStart = Math.max(lastStart, segment.start);
  };

  /** @param {Job} current */
  const describe = (current) => {
    if (current.status === 'queued') return 'A transcrição começa quando chegar a vez deste arquivo.';
    if (current.status === 'downloading_model') return 'Baixando o modelo; o texto aparece logo em seguida.';
    if (ACTIVE_STATUSES.has(current.status)) return 'Transcrevendo… o texto aparece aqui conforme sai.';
    if (rows.length === 0) return 'Nenhum texto transcrito.';
    if (current.status === 'completed') return '';
    return 'Texto transcrito até a interrupção.';
  };

  /** @param {Job} current */
  const update = async (current) => {
    const fresh = await loadSegments(current.id, lastStart);
    fresh.forEach(addRow);
    if (current.files.vtt && current.files.vtt !== trackSrc && isVideo) {
      trackSrc = current.files.vtt;
      player.replaceChildren(el('track', {
        kind: 'subtitles', srclang: 'pt', label: 'Legenda', src: trackSrc, default: true,
      }));
    }
    status.textContent = describe(current);
  };

  const destroy = () => { player.pause(); player.removeAttribute('src'); player.load(); };

  return { element, update, destroy };
}
