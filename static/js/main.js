/** Page entry point: loads options, renders the history and polls for updates. */

import { POLL_INTERVAL_MS } from './contract.js';
import { openAnalysis } from './analysis-dialog.js';
import { createJobsView } from './jobs-view.js';
import * as api from './api.js';
import { ApiError } from './api.js';
import { setupUpload } from './upload-view.js';

/** @typedef {import('./contract.js').Job} Job */

const jobsContainer = document.getElementById('jobsList');
const notification = document.getElementById('notification');
const notificationText = document.getElementById('notificationText');
const deleteDialog = /** @type {HTMLDialogElement} */ (document.getElementById('deleteDialog'));

/** @type {{render: (jobs: Job[]) => void}} */
let jobsView;
let notifyTimer = 0;

/**
 * Show a short message at the bottom of the page.
 * @param {string} message
 * @param {string} [tone]
 */
function notify(message, tone = 'success') {
  notificationText.textContent = message;
  notification.className = `notification notification--${tone}`;
  notification.hidden = false;
  clearTimeout(notifyTimer);
  notifyTimer = setTimeout(() => { notification.hidden = true; }, 4000);
}

/**
 * Ask for confirmation in a dialog (never window.confirm).
 * @param {Job} job
 * @returns {Promise<boolean>}
 */
function confirmDelete(job) {
  document.getElementById('deleteFileName').textContent = job.filename;
  deleteDialog.returnValue = '';
  deleteDialog.showModal();
  return new Promise((resolve) => {
    deleteDialog.addEventListener('close', () => resolve(deleteDialog.returnValue === 'confirm'), { once: true });
  });
}

/**
 * Run an API action, show its result and refresh the list.
 * @param {() => Promise<unknown>} action
 * @param {string} success
 * @param {string} [tone]
 * @returns {Promise<boolean>} Whether the action succeeded.
 */
async function attempt(action, success, tone = 'success') {
  let ok = false;
  try {
    await action();
    notify(success, tone);
    ok = true;
  } catch (error) {
    notify(error instanceof ApiError ? error.message : 'Algo deu errado. Tente de novo.', 'error');
  }
  await refresh();
  return ok;
}

/**
 * Show the Análise da Mídia modal and confirm the decision.
 * @param {Job} job  A job awaiting a decision.
 * @param {import('./contract.js').Options} options
 * @param {{language: string, model: string, device: string}} initial
 * @returns {Promise<boolean>} True when the job was sent to the queue.
 */
async function decide(job, options, initial) {
  const decision = await openAnalysis(job, options, initial);
  if (!decision) {
    notify('Tudo bem: o arquivo fica aguardando sua decisão na lista.', 'warning');
    await refresh();
    return false;
  }
  return attempt(() => api.confirmJob(job.id, decision), 'Na fila! A transcrição começa assim que houver vez.');
}

/** Fetch and render the history. */
async function refresh() {
  try {
    jobsView.render(await api.listJobs());
  } catch (error) {
    notify(error instanceof ApiError ? error.message : 'Não foi possível atualizar a lista.', 'error');
  }
}

async function start() {
  const options = await api.getOptions();
  const languageLabels = Object.fromEntries(options.languages.map((item) => [item.code, item.label]));
  jobsView = createJobsView(jobsContainer, languageLabels, {
    decide: (job) => decide(job, options, { language: job.language, model: job.model, device: job.device }),
    cancel: (job) => attempt(() => api.cancelJob(job.id), 'Processamento cancelado.', 'warning'),
    retry: (job) => attempt(() => api.retryJob(job.id), 'Enviado de volta para a fila.'),
    remove: async (job) => {
      if (!(await confirmDelete(job))) return;
      await attempt(() => api.deleteJob(job.id), 'Arquivos excluídos.');
    },
    loadSegments: (id, after) => api.getSegments(id, after).catch(() => []),
  });
  setupUpload(
    options,
    async (file, choices) => {
      let job;
      try {
        job = await api.createJob(file, choices);
      } catch (error) {
        notify(error instanceof ApiError ? error.message : 'Não foi possível enviar o arquivo.', 'error');
        return false;
      }
      await refresh();
      await decide(job, options, choices);
      return true;
    },
    notify,
  );
  await refresh();
  setInterval(refresh, POLL_INTERVAL_MS);
}

start().catch((error) => {
  console.error(error);
  notify('Não foi possível carregar a página. Confira se o app está rodando.', 'error');
});
