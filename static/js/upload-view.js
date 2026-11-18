/** Upload card: media picker, per-job options and validation. */

import { el, formatSize } from './dom.js';

/** @typedef {import('./contract.js').Options} Options */

/**
 * Wire the upload card.
 * @param {Options} options
 * @param {(file: File, choices: {language: string, model: string, device: string}) => Promise<boolean>} onSubmit
 *   Resolves true when the upload was accepted.
 * @param {(message: string, tone?: string) => void} notify
 */
export function setupUpload(options, onSubmit, notify) {
  const area = document.getElementById('uploadArea');
  const input = /** @type {HTMLInputElement} */ (document.getElementById('fileInput'));
  const selected = document.getElementById('fileSelected');
  const fileName = document.getElementById('fileName');
  const fileSize = document.getElementById('fileSize');
  const submit = /** @type {HTMLButtonElement} */ (document.getElementById('submitBtn'));
  const language = /** @type {HTMLSelectElement} */ (document.getElementById('languageSelect'));
  const model = /** @type {HTMLSelectElement} */ (document.getElementById('modelSelect'));
  const device = /** @type {HTMLSelectElement} */ (document.getElementById('deviceSelect'));
  const deviceHint = document.getElementById('deviceHint');
  const modelHint = document.getElementById('modelHint');

  const extensions = options.accepted_extensions;
  input.accept = extensions.map((ext) => `.${ext}`).join(',');
  document.getElementById('acceptedFormats').textContent = (
    `${extensions.map((ext) => ext.toUpperCase()).join(', ')} · até ${formatSize(options.max_upload_mb * 1024 * 1024)}`
  );

  language.replaceChildren(...options.languages.map((item) => el('option', {
    value: item.code, text: item.label, selected: item.code === options.default_language,
  })));
  model.replaceChildren(...options.models.map((item) => el('option', {
    value: item.name, text: item.label, selected: item.name === options.default_model,
  })));
  const showModelHint = () => {
    const chosen = options.models.find((item) => item.name === model.value);
    modelHint.textContent = chosen ? chosen.hint : '';
  };
  model.addEventListener('change', showModelHint);
  showModelHint();

  const gpuOption = /** @type {HTMLOptionElement} */ (device.querySelector('option[value="gpu"]'));
  gpuOption.disabled = !options.gpu_available;
  deviceHint.textContent = options.gpu_available
    ? 'GPU NVIDIA detectada.'
    : 'GPU indisponível. Para usar, inicie com o arquivo docker-compose.gpu.yml.';

  /** @type {File|null} */
  let file = null;

  /** @param {File} candidate */
  const choose = (candidate) => {
    const ext = candidate.name.split('.').pop().toLowerCase();
    if (!extensions.includes(ext)) {
      notify(`Formato .${ext} não suportado.`, 'error');
      return;
    }
    if (candidate.size > options.max_upload_mb * 1024 * 1024) {
      notify(`Arquivo maior que ${formatSize(options.max_upload_mb * 1024 * 1024)}.`, 'error');
      return;
    }
    file = candidate;
    fileName.textContent = candidate.name;
    fileSize.textContent = formatSize(candidate.size);
    selected.hidden = false;
  };

  area.addEventListener('click', () => input.click());
  area.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); input.click(); }
  });
  input.addEventListener('change', () => { if (input.files[0]) choose(input.files[0]); });
  area.addEventListener('dragover', (event) => { event.preventDefault(); area.classList.add('drag-over'); });
  area.addEventListener('dragleave', () => area.classList.remove('drag-over'));
  area.addEventListener('drop', (event) => {
    event.preventDefault();
    area.classList.remove('drag-over');
    if (event.dataTransfer.files[0]) choose(event.dataTransfer.files[0]);
  });

  document.getElementById('clearFileBtn').addEventListener('click', () => {
    file = null;
    input.value = '';
    selected.hidden = true;
  });

  submit.addEventListener('click', async () => {
    if (!file) return;
    submit.disabled = true;
    try {
      const accepted = await onSubmit(
        file, { language: language.value, model: model.value, device: device.value },
      );
      if (accepted) {
        file = null;
        input.value = '';
        selected.hidden = true;
      }
    } finally {
      submit.disabled = false;
    }
  });
}
