/**
 * Job history. Cards are keyed by job id and updated in place, so the open
 * card keeps its player while the list refreshes every few seconds.
 */

import {
  ACTIVE_STATUSES, DEVICE_LABELS, RETRYABLE_STATUSES, STATUS,
} from './contract.js';
import {
  el, formatDate, formatDuration, icon,
} from './dom.js';
import { createDetail } from './job-detail.js';

/** @typedef {import('./contract.js').Job} Job */
/** @typedef {import('./contract.js').Segment} Segment */
/** @typedef {import('./job-detail.js').JobDetail} JobDetail */

/**
 * @typedef {Object} JobActions
 * @property {(job: Job) => void} decide  Reopen the Análise da Mídia modal.
 * @property {(job: Job) => void} cancel
 * @property {(job: Job) => void} retry
 * @property {(job: Job) => void} remove
 * @property {(id: string, after: number) => Promise<Segment[]>} loadSegments
 */

const DOWNLOADS = [
  { key: 'video', label: 'Vídeo legendado', icon: 'video' },
  { key: 'srt', label: 'SRT', icon: 'closed-captioning' },
  { key: 'vtt', label: 'VTT', icon: 'file-code' },
  { key: 'txt', label: 'Texto', icon: 'file-lines' },
  { key: 'json', label: 'JSON', icon: 'code' },
];

/**
 * Create the history list controller.
 * @param {HTMLElement} container
 * @param {Object<string, string>} languageLabels  code -> pt-BR label
 * @param {JobActions} actions
 * @returns {{render: (jobs: Job[]) => void}}
 */
export function createJobsView(container, languageLabels, actions) {
  /** @type {Map<string, {card: HTMLElement, summary: HTMLElement}>} */
  const cards = new Map();
  /** @type {{id: string, detail: JobDetail}|null} */
  let open = null;
  /** @type {Map<string, Job>} */
  let latest = new Map();

  const close = () => {
    if (!open) return;
    open.detail.destroy();
    const entry = cards.get(open.id);
    if (entry) {
      open.detail.element.remove();
      entry.card.classList.remove('is-open');
      entry.summary.setAttribute('aria-expanded', 'false');
    }
    open = null;
  };

  /** @param {string} id */
  const toggle = (id) => {
    const wasOpen = open && open.id === id;
    close();
    if (wasOpen) return;
    const job = latest.get(id);
    const entry = cards.get(id);
    if (!job || !entry) return;
    const detail = createDetail(job, actions.loadSegments);
    entry.card.append(detail.element);
    entry.card.classList.add('is-open');
    entry.summary.setAttribute('aria-expanded', 'true');
    open = { id, detail };
    detail.update(job);
    entry.card.scrollIntoView({ block: 'start', behavior: 'smooth' });
  };

  /** @param {Job[]} jobs */
  const render = (jobs) => {
    latest = new Map(jobs.map((job) => [job.id, job]));
    if (open && !latest.has(open.id)) close();

    if (jobs.length === 0) {
      cards.clear();
      container.replaceChildren(el('p', { class: 'jobs-empty', text: 'Nenhum vídeo ainda. Envie o primeiro acima.' }));
      return;
    }

    const ordered = jobs.map((job) => {
      let entry = cards.get(job.id);
      if (!entry) {
        const summary = el('div', {
          class: 'job-card__summary', role: 'button', tabindex: 0, 'aria-expanded': 'false',
        });
        const card = el('article', { class: 'job-card' }, [summary]);
        summary.addEventListener('click', (event) => {
          if (event.target.closest('a, button')) return;
          toggle(job.id);
        });
        summary.addEventListener('keydown', (event) => {
          if (event.target !== summary) return;
          if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggle(job.id); }
        });
        entry = { card, summary };
        cards.set(job.id, entry);
      }
      entry.card.className = `job-card job-card--${STATUS[job.status].tone}${open && open.id === job.id ? ' is-open' : ''}`;
      entry.summary.replaceChildren(...summaryContent(job, languageLabels, actions).filter(Boolean));
      entry.summary.setAttribute('aria-label', `${job.filename}: ${STATUS[job.status].label}. Abrir detalhes`);
      return entry.card;
    });

    for (const id of [...cards.keys()]) if (!latest.has(id)) cards.delete(id);
    container.replaceChildren(...ordered);
    if (open) open.detail.update(latest.get(open.id));
  };

  return { render };
}

/**
 * @param {Job} job
 * @param {Object<string, string>} languageLabels
 * @param {JobActions} actions
 * @returns {(HTMLElement|null)[]}
 */
function summaryContent(job, languageLabels, actions) {
  const status = STATUS[job.status];
  const active = ACTIVE_STATUSES.has(job.status);
  const meta = [
    formatDate(job.created_at),
    job.duration_seconds ? formatDuration(job.duration_seconds) : null,
    languageLabels[job.language] || job.language,
    `Modelo ${job.model}`,
    DEVICE_LABELS[job.device],
  ].filter(Boolean).join(' · ');

  return [
    el('div', { class: 'job-card__head' }, [
      el('div', { class: 'job-card__title' }, [
        icon(job.media_kind === 'audio' ? 'file-audio' : 'file-video'),
        el('h3', { text: job.filename, title: job.filename }),
      ]),
      el('span', { class: `status status--${status.tone}`, text: status.label }),
    ]),
    el('p', { class: 'job-card__meta', text: meta }),
    active ? progress(job) : null,
    job.status === 'failed' && job.error
      ? el('p', { class: 'job-card__error', role: 'alert' }, [icon('triangle-exclamation'), ` ${job.error}`])
      : null,
    !active && job.status !== 'failed' && job.step_label !== status.label
      ? el('p', { class: 'job-card__note', text: job.step_label })
      : null,
    job.status === 'completed' ? downloads(job) : null,
    el('div', { class: 'job-card__actions' }, buttons(job, actions)),
  ];
}

/** @param {Job} job */
function progress(job) {
  return el('div', { class: 'job-progress' }, [
    el('div', {
      class: 'progress-bar', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': 100,
      'aria-valuenow': job.progress, 'aria-label': `Progresso de ${job.filename}`,
    }, [el('div', { class: 'progress-fill', style: `width: ${job.progress}%` })]),
    el('div', { class: 'progress-text' }, [
      el('span', { text: job.step_label }),
      el('span', { text: `${job.progress}%` }),
    ]),
  ]);
}

/** @param {Job} job */
function downloads(job) {
  const links = DOWNLOADS
    .filter((item) => job.files[item.key])
    .map((item) => el('a', {
      class: 'download-chip', href: job.files[item.key], download: true,
    }, [icon(item.icon), ` ${item.label}`]));
  return el('div', { class: 'job-card__downloads' }, links);
}

/**
 * @param {Job} job
 * @param {JobActions} actions
 * @returns {HTMLElement[]}
 */
function buttons(job, actions) {
  const list = [];
  if (job.status === 'awaiting_decision') {
    list.push(button('Continuar', 'list-check', 'btn--primary', () => actions.decide(job)));
  }
  if (job.status === 'completed') {
    list.push(el('button', {
      class: 'btn btn--outline btn--sm', type: 'button', disabled: true,
      title: 'Disponível em breve (Fase 3)',
    }, [icon('wand-magic-sparkles'), ' Revisar com IA']));
  }
  if (ACTIVE_STATUSES.has(job.status)) {
    list.push(button('Cancelar', 'stop', 'btn--outline', () => actions.cancel(job)));
  }
  if (RETRYABLE_STATUSES.has(job.status)) {
    list.push(button('Reprocessar', 'rotate-right', 'btn--secondary', () => actions.retry(job)));
  }
  if (!ACTIVE_STATUSES.has(job.status)) {
    list.push(button('Excluir', 'trash', 'btn--danger', () => actions.remove(job)));
  }
  return list;
}

/**
 * @param {string} label
 * @param {string} iconName
 * @param {string} variant
 * @param {() => void} onClick
 */
function button(label, iconName, variant, onClick) {
  return el('button', { class: `btn ${variant} btn--sm`, type: 'button', onClick }, [icon(iconName), ` ${label}`]);
}
