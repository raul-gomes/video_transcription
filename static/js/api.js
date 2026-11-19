/** Client for the backend API. Shapes are documented in contract.js. */

/** @typedef {import('./contract.js').Job} Job */
/** @typedef {import('./contract.js').Options} Options */
/** @typedef {import('./contract.js').Segment} Segment */

/** Error with a pt-BR message from the backend, safe to show. */
export class ApiError extends Error {}

const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

/**
 * Call the API and parse JSON.
 * @param {string} url
 * @param {RequestInit} [init]
 * @returns {Promise<any>}
 */
async function request(url, init = {}) {
  const headers = { Accept: 'application/json', ...(init.headers || {}) };
  if (init.method && init.method !== 'GET') headers['X-CSRFToken'] = csrfToken();
  let response;
  try {
    response = await fetch(url, { ...init, headers, credentials: 'same-origin' });
  } catch {
    throw new ApiError('Sem conexão com o app. Confira se ele está rodando.');
  }
  if (response.status === 204) return null;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError((body && body.detail) || `Erro ${response.status} no servidor.`);
  }
  return body;
}

/** @returns {Promise<Options>} */
export const getOptions = () => request('/api/options/');

/** @returns {Promise<Job[]>} Newest first. */
export const listJobs = () => request('/api/jobs/');

/**
 * Upload a file with the chosen options.
 * @param {File} file
 * @param {{language: string, model: string, device: string}} choices
 * @returns {Promise<Job>}
 */
export function createJob(file, choices) {
  const form = new FormData();
  form.append('media', file);
  form.append('language', choices.language);
  form.append('model', choices.model);
  form.append('device', choices.device);
  return request('/api/jobs/', { method: 'POST', body: form });
}

/**
 * Confirm the Análise da Mídia decision; the job enters the queue.
 * @param {string} id
 * @param {import('./contract.js').Decision} decision
 * @returns {Promise<Job>}
 */
export const confirmJob = (id, decision) => request(`/api/jobs/${encodeURIComponent(id)}/confirm/`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(decision),
});

/** @param {string} id @returns {Promise<Job>} */
export const cancelJob = (id) => request(`/api/jobs/${encodeURIComponent(id)}/cancel/`, { method: 'POST' });

/** @param {string} id @returns {Promise<Job>} */
export const retryJob = (id) => request(`/api/jobs/${encodeURIComponent(id)}/retry/`, { method: 'POST' });

/** @param {string} id @returns {Promise<null>} */
export const deleteJob = (id) => request(`/api/jobs/${encodeURIComponent(id)}/`, { method: 'DELETE' });

/**
 * Segments starting after ``after`` seconds.
 * @param {string} id
 * @param {number} [after]
 * @returns {Promise<Segment[]>}
 */
export const getSegments = (id, after = -1) => request(
  `/api/jobs/${encodeURIComponent(id)}/segments/?after=${encodeURIComponent(after)}`,
);
