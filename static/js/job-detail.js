/**
 * Expanded area of a job card: media player plus the transcript, which grows
 * while the job runs. Created once per opening so polling never restarts playback.
 *
 * While the job runs, the player never passes the Fronteira da transcrição (end of
 * the last transcribed Trecho): it pauses there and resumes once the transcript is
 * RESUME_AHEAD_SECONDS ahead. Seeking past the Fronteira turns that off until the
 * person is back behind it (ADR 0003).
 */

import { ACTIVE_STATUSES, RESUME_AHEAD_SECONDS } from './contract.js';
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
    class: 'job-detail__player', controls: true, preload: 'metadata', src: job.files.preview || job.files.media,
  }));
  const list = el('ol', { class: 'transcript', 'aria-label': 'Transcrição' });
  const status = el('p', { class: 'transcript__status' });
  /** @type {{segment: Segment, item: HTMLElement}[]} */
  const rows = [];
  let lastStart = -1;
  let trackSrc = null;
  let usingPreview = Boolean(job.files.preview);
  let running = ACTIVE_STATUSES.has(job.status);
  /** End of the last transcribed Trecho, in media seconds. */
  let frontier = 0;
  /** The player is paused because it reached the Fronteira (not by the person). */
  let waiting = false;
  /** The person sought past the Fronteira: no automatic pause until they come back. */
  let ahead = false;
  const waitNote = el('p', { class: 'job-detail__wait', role: 'status', hidden: true }, [
    'Aguardando a transcrição…',
  ]);

  const element = el('div', { class: 'job-detail' }, [
    el('div', { class: 'job-detail__media' }, [player, waitNote]),
    el('div', { class: 'job-detail__text' }, [
      el('h4', { class: 'job-detail__title', text: 'Transcrição' }),
      list,
      status,
    ]),
  ]);

  /** @param {boolean} on */
  const setWaiting = (on) => {
    waiting = on;
    waitNote.hidden = !on;
  };

  /** Pause at the Fronteira while the job runs, unless the person went past it on purpose. */
  const holdAtFrontier = () => {
    if (!running || player.paused) return;
    if (ahead && player.currentTime < frontier) ahead = false;
    if (!ahead && player.currentTime >= frontier) {
      player.pause();
      setWaiting(true);
    }
  };

  /** Resume a waiting player once there is enough transcript ahead of it. */
  const resumeIfReady = () => {
    if (!waiting) return;
    if (!running || frontier > player.currentTime + RESUME_AHEAD_SECONDS) {
      setWaiting(false);
      player.play().catch(() => {});
    }
  };

  player.addEventListener('timeupdate', () => {
    const now = player.currentTime;
    for (const { segment, item } of rows) {
      item.classList.toggle('is-current', now >= segment.start && now < segment.end);
    }
    holdAtFrontier();
  });
  player.addEventListener('play', () => {
    setWaiting(false);
    holdAtFrontier();
  });
  player.addEventListener('seeking', () => {
    if (!running) return;
    ahead = player.currentTime > frontier;
    if (ahead) setWaiting(false);
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
    frontier = Math.max(frontier, segment.end);
  };

  /** @param {Job} current */
  const describe = (current) => {
    if (current.status === 'awaiting_decision') return 'Confirme a análise do arquivo para começar.';
    if (current.status === 'preparing_preview') return 'Preparando a prévia; o som aparece quando ela ficar pronta.';
    if (current.status === 'queued') return 'A transcrição começa quando chegar a vez deste arquivo.';
    if (current.status === 'downloading_model') return 'Baixando o modelo; o texto aparece logo em seguida.';
    if (ACTIVE_STATUSES.has(current.status)) return 'Transcrevendo… o texto aparece aqui conforme sai.';
    if (rows.length === 0) return 'Nenhum texto transcrito.';
    if (current.status === 'completed') return '';
    return 'Texto transcrito até a interrupção.';
  };

  /** @param {Job} current */
  const update = async (current) => {
    if (current.files.preview && !usingPreview) {
      // The Prévia just became ready: switch the player to it, keeping the position.
      usingPreview = true;
      const at = player.currentTime;
      player.src = current.files.preview;
      player.addEventListener('loadedmetadata', () => { player.currentTime = at; }, { once: true });
    }
    running = ACTIVE_STATUSES.has(current.status);
    const fresh = await loadSegments(current.id, lastStart);
    fresh.forEach(addRow);
    if (current.files.vtt && isVideo) {
      // The VTT is rewritten after each Bloco under the same URL: version it by the
      // Fronteira so the browser fetches the new cues instead of its cached copy.
      const src = running ? `${current.files.vtt}?v=${frontier.toFixed(1)}` : current.files.vtt;
      if (src !== trackSrc) {
        trackSrc = src;
        player.replaceChildren(el('track', {
          kind: 'subtitles', srclang: current.detected_language || (current.language === 'auto' ? 'und' : current.language),
          label: 'Legenda', src, default: true,
        }));
      }
    }
    resumeIfReady();
    status.textContent = describe(current);
  };

  const destroy = () => { player.pause(); player.removeAttribute('src'); player.load(); };

  return { element, update, destroy };
}
