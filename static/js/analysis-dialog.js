/**
 * Análise da Mídia modal: shows what the file contains and what this browser can
 * play, and collects the person's decision before the job enters the queue.
 */

import { TRACK_LANGUAGE_TO_CODE } from './contract.js';
import {
  el, formatDuration, formatSize, icon,
} from './dom.js';

/** @typedef {import('./contract.js').Job} Job */
/** @typedef {import('./contract.js').Options} Options */
/** @typedef {import('./contract.js').AudioTrack} AudioTrack */
/** @typedef {import('./contract.js').Decision} Decision */

/** Containers browsers open directly in a <video> element. */
const BROWSER_CONTAINERS = new Set(['MP4', 'WEBM', 'MP3', 'M4A', 'WAV', 'OGG']);

/**
 * Whether this browser can play a media type (empty string means "no").
 * @param {string} mime
 * @returns {boolean}
 */
function canPlay(mime) {
  const probe = document.createElement(mime.startsWith('audio') ? 'audio' : 'video');
  return probe.canPlayType(mime) !== '';
}

/** @param {boolean} ok */
function playBadge(ok) {
  return el('span', {
    class: `status status--${ok ? 'success' : 'error'}`,
    text: ok ? 'Toca no navegador' : 'Não toca no navegador',
  });
}

/** @param {AudioTrack} track */
function trackName(track) {
  return track.title || (track.language ? track.language.toUpperCase() : `Faixa ${track.index}`);
}

/**
 * Pick the default track: the one in the chosen language, otherwise the first.
 * @param {AudioTrack[]} tracks
 * @param {string} language  App language code (pt, en, es, auto).
 * @returns {AudioTrack}
 */
function defaultTrack(tracks, language) {
  return tracks.find((track) => TRACK_LANGUAGE_TO_CODE[track.language] === language) || tracks[0];
}

/**
 * Open the modal for a job awaiting a decision.
 * @param {Job} job
 * @param {Options} options
 * @param {{language: string, model: string, device: string}} initial  Upload-card choices.
 * @returns {Promise<Decision|null>} Null when the person decides later.
 */
export function openAnalysis(job, options, initial) {
  const analysis = job.analysis;
  const videoOk = analysis.video ? canPlay(analysis.video.mime) : true;
  const containerOk = analysis.browser_container || BROWSER_CONTAINERS.has(analysis.format_label);
  let selected = defaultTrack(analysis.audio_tracks, initial.language);

  const language = /** @type {HTMLSelectElement} */ (el('select', { class: 'form-control', id: 'decisionLanguage' },
    options.languages.map((item) => el('option', { value: item.code, text: item.label, selected: item.code === initial.language }))));
  const trackCode = TRACK_LANGUAGE_TO_CODE[selected.language];
  if (trackCode) language.value = trackCode;
  const model = /** @type {HTMLSelectElement} */ (el('select', { class: 'form-control', id: 'decisionModel' },
    options.models.map((item) => el('option', { value: item.name, text: `${item.label} — ${item.hint}`, selected: item.name === initial.model }))));
  const device = /** @type {HTMLSelectElement} */ (el('select', { class: 'form-control', id: 'decisionDevice' }, [
    el('option', { value: 'auto', text: 'Automático', selected: initial.device === 'auto' }),
    el('option', { value: 'cpu', text: 'CPU', selected: initial.device === 'cpu' }),
    el('option', { value: 'gpu', text: options.gpu_available ? 'GPU' : 'GPU (indisponível)', disabled: !options.gpu_available, selected: initial.device === 'gpu' }),
  ]));

  const preview = /** @type {HTMLInputElement} */ (el('input', { type: 'checkbox', id: 'decisionPreview' }));
  const convertVideo = /** @type {HTMLInputElement} */ (el('input', { type: 'checkbox', id: 'decisionConvertVideo' }));
  const previewReason = el('p', { class: 'form-hint' });
  const alerts = el('div', { class: 'analysis-alerts' });

  /** Recompute alerts and the preview suggestion for the selected track. */
  const refresh = () => {
    const audioOk = canPlay(selected.mime);
    const reasons = [];
    if (!audioOk) reasons.push(`o áudio ${selected.codec_label} não toca neste navegador`);
    if (!containerOk) reasons.push(`o formato ${analysis.format_label} não abre direto no navegador`);
    preview.checked = reasons.length > 0;
    previewReason.textContent = reasons.length
      ? `Recomendado porque ${reasons.join(' e ')}. Ocupa cerca de ${formatSize(analysis.size_bytes)} a mais no disco.`
      : `Não é necessária: o arquivo já toca com som. Ocupa cerca de ${formatSize(analysis.size_bytes)} a mais no disco.`;

    const items = [];
    if (analysis.audio_tracks.length > 1) {
      items.push(['circle-info', 'info', `Este arquivo tem ${analysis.audio_tracks.length} faixas de áudio. Escolha qual transcrever.`]);
    }
    if (!audioOk) items.push(['volume-xmark', 'warning', `Sem som no navegador: a faixa escolhida é ${selected.codec_label}. A prévia converte o áudio; o arquivo final mantém o original.`]);
    if (!videoOk) items.push(['eye-slash', 'warning', `A imagem ${analysis.video.codec_label} não aparece neste navegador. A transcrição funciona normalmente.`]);
    alerts.replaceChildren(...items.map(([name, tone, text]) => el('p', { class: `analysis-alert analysis-alert--${tone}` }, [icon(name), ` ${text}`])));
  };

  const trackRows = analysis.audio_tracks.map((track) => {
    const radio = el('input', {
      type: 'radio', name: 'audioTrack', value: track.index, checked: track === selected,
      onChange: () => {
        selected = track;
        const code = TRACK_LANGUAGE_TO_CODE[track.language];
        if (code) language.value = code;
        refresh();
      },
    });
    return el('label', { class: 'analysis-track' }, [
      radio,
      el('span', { class: 'analysis-track__name', text: trackName(track) }),
      el('span', { class: 'analysis-track__meta', text: `${track.codec_label} · ${track.channel_label}` }),
      playBadge(canPlay(track.mime)),
    ]);
  });

  const subtitles = analysis.subtitles.length
    ? el('p', { class: 'analysis-muted', text: `${analysis.subtitles.length} legenda(s) no arquivo: ${analysis.subtitles.map((sub) => sub.title || sub.language || 'sem nome').join(', ')}. Por enquanto são só informativas.` })
    : el('p', { class: 'analysis-muted', text: 'Nenhuma legenda no arquivo.' });

  const general = [
    analysis.format_label,
    formatSize(analysis.size_bytes),
    analysis.duration_seconds ? formatDuration(analysis.duration_seconds) : null,
  ].filter(Boolean).join(' · ');

  const dialog = /** @type {HTMLDialogElement} */ (el('dialog', { class: 'dialog dialog--wide analysis-dialog', 'aria-labelledby': 'analysisTitle' }, [
    el('form', { method: 'dialog' }, [
      el('h3', { id: 'analysisTitle', text: 'Análise do arquivo' }),
      el('p', { class: 'analysis-file' }, [icon(analysis.video ? 'file-video' : 'file-audio'), ` ${job.filename}`, el('span', { class: 'analysis-muted', text: ` · ${general}` })]),
      alerts,
      analysis.video ? el('section', { class: 'analysis-section' }, [
        el('h4', { text: 'Vídeo' }),
        el('div', { class: 'analysis-row' }, [
          el('span', { text: `${analysis.video.codec_label} · ${analysis.video.width}×${analysis.video.height}` }),
          playBadge(videoOk),
        ]),
      ]) : null,
      el('section', { class: 'analysis-section' }, [
        el('h4', { text: analysis.audio_tracks.length > 1 ? 'Faixas de áudio (escolha uma)' : 'Faixa de áudio' }),
        ...trackRows,
      ]),
      el('section', { class: 'analysis-section' }, [el('h4', { text: 'Legendas embutidas' }), subtitles]),
      el('section', { class: 'analysis-section' }, [
        el('h4', { text: 'Transcrição' }),
        el('div', { class: 'job-options' }, [
          el('div', { class: 'form-group' }, [el('label', { class: 'form-label', for: 'decisionLanguage', text: 'Idioma da fala' }), language]),
          el('div', { class: 'form-group' }, [el('label', { class: 'form-label', for: 'decisionModel', text: 'Modelo do Whisper' }), model]),
          el('div', { class: 'form-group' }, [el('label', { class: 'form-label', for: 'decisionDevice', text: 'Processar com' }), device]),
        ]),
      ]),
      el('section', { class: 'analysis-section' }, [
        el('h4', { text: 'Assistir no navegador' }),
        el('label', { class: 'analysis-check' }, [preview, ' Preparar prévia para assistir com som no navegador']),
        previewReason,
        !videoOk ? el('label', { class: 'analysis-check' }, [convertVideo, ' Converter também a imagem (pode demorar bastante)']) : null,
      ]),
      el('div', { class: 'dialog__actions' }, [
        el('button', { class: 'btn btn--outline', value: 'later', text: 'Decidir depois' }),
        el('button', { class: 'btn btn--primary', value: 'start' }, [icon('play'), ' Começar transcrição']),
      ]),
    ]),
  ]));

  refresh();
  document.body.append(dialog);
  dialog.showModal();

  return new Promise((resolve) => {
    dialog.addEventListener('close', () => {
      const start = dialog.returnValue === 'start';
      dialog.remove();
      resolve(start ? {
        audio_track: selected.index,
        language: language.value,
        model: model.value,
        device: /** @type {'auto'|'cpu'|'gpu'} */ (device.value),
        preview: preview.checked,
        convert_video: preview.checked && convertVideo.checked,
      } : null);
    }, { once: true });
  });
}
