/* ==========================================================================
   Video Transcription — lógica de upload, player e legenda em tempo real
   ========================================================================== */

const POLL_INTERVAL_MS = 2000;

const state = {
  file: null,
  localUrl: null,
  jobId: null,
  processing: false,
  pollTimer: null,
  rendered: 0,
  segments: [],
  elByIndex: [],
  activeIndex: -1,
  subtitlesOn: true,
  files: {},
  playStarted: false,   // já liberamos a reprodução?
  waiting: false,       // pausado esperando a transcrição alcançar?
  completed: false,     // transcrição terminou?
};

// ---------------------------------------------------------------- elementos
const el = (id) => document.getElementById(id);

const uploadSection   = el('uploadSection');
const uploadArea      = el('uploadArea');
const fileInput       = el('fileInput');
const fileSelected    = el('fileSelected');
const fileName        = el('fileName');
const fileSize        = el('fileSize');
const processBtn      = el('processBtn');
const languageSelect  = el('languageSelect');

const playerSection   = el('playerSection');
const videoPlayer     = el('videoPlayer');
const liveCaption     = el('liveCaption');
const playerFileName  = el('playerFileName');
const toggleSubtitles = el('toggleSubtitles');

const playerOverlay      = el('playerOverlay');
const overlaySpinner     = el('overlaySpinner');
const overlayPlayBtn     = el('overlayPlayBtn');
const playerOverlayTitle = el('playerOverlayTitle');
const playerOverlayStep  = el('playerOverlayStep');

const downloadSection = el('downloadSection');
const resetBtn        = el('resetBtn');

const progressFill    = el('progressFill');
const progressLabel   = el('progressLabel');
const progressPercent = el('progressPercent');
const statusText      = el('statusText');
const statusDot       = el('statusDot');

const transcriptList  = el('transcriptList');
const transcriptEmpty = el('transcriptEmpty');
const segmentCount    = el('segmentCount');
const languageBadge   = el('languageBadge');

const notification    = el('notification');
const notificationText = el('notificationText');
const notificationIcon = el('notificationIcon');

const csrftoken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

const VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'];

const STATUS = {
  pending:      { label: 'Na fila de processamento…', short: 'Na fila',        color: '#94a3b8' },
  extracting:   { label: 'Extraindo o áudio do vídeo…', short: 'Extraindo áudio', color: '#fbbf24' },
  transcribing: { label: 'Transcrevendo com Whisper…', short: 'Transcrevendo',  color: '#3fadbd' },
  generating:   { label: 'Gerando arquivos de legenda…', short: 'Gerando legendas', color: '#fbbf24' },
  completed:    { label: 'Processamento concluído!', short: 'Concluído',       color: '#34d399' },
  failed:       { label: 'Falha no processamento', short: 'Erro',              color: '#f87171' },
};

// ---------------------------------------------------------------- utilidades
function formatTime(seconds) {
  seconds = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = String(m).padStart(2, '0');
  const ss = String(s).padStart(2, '0');
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

function formatFileSize(bytes) {
  if (!bytes) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

function showNotification(message, type = 'info') {
  notificationText.textContent = message;
  notification.className = notification.className.replace(/is-(success|error|info)/g, '').trim();
  notification.classList.add(`is-${type}`);
  notificationIcon.className = 'fas ' + (
    type === 'success' ? 'fa-circle-check' :
    type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-info'
  );
  notification.style.display = 'flex';
  notification.style.opacity = '1';
  clearTimeout(showNotification._t);
  showNotification._t = setTimeout(() => {
    notification.style.opacity = '0';
    setTimeout(() => { notification.style.display = 'none'; }, 250);
  }, 4000);
}

function setProgress(percent, label) {
  percent = Math.max(0, Math.min(100, Math.round(percent || 0)));
  progressFill.style.width = `${percent}%`;
  progressPercent.textContent = `${percent}%`;
  if (label) progressLabel.textContent = label;
}

function setStatus(status) {
  const info = STATUS[status] || { short: status, color: '#94a3b8' };
  statusText.textContent = info.short;
  statusDot.style.backgroundColor = info.color;
}

// ---------------------------------------------------------------- upload
uploadArea.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
  const file = e.target.files?.[0];
  if (file) handleFileSelection(file);
});

['dragover', 'dragenter'].forEach((evt) =>
  uploadArea.addEventListener(evt, (e) => {
    e.preventDefault();
    uploadArea.classList.add('border-brand-400', 'bg-brand-500/5');
  })
);
['dragleave', 'drop'].forEach((evt) =>
  uploadArea.addEventListener(evt, (e) => {
    e.preventDefault();
    uploadArea.classList.remove('border-brand-400', 'bg-brand-500/5');
  })
);
uploadArea.addEventListener('drop', (e) => {
  const file = e.dataTransfer?.files?.[0];
  if (file) handleFileSelection(file);
});

function handleFileSelection(file) {
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!VIDEO_FORMATS.includes(ext)) {
    showNotification('Formato não suportado. Use: MP4, AVI, MOV, MKV, WEBM, FLV, WMV', 'error');
    return;
  }
  state.file = file;
  fileName.textContent = file.name;
  fileSize.textContent = formatFileSize(file.size);
  fileSelected.classList.remove('hidden');
  fileSelected.classList.add('flex');
}

processBtn.addEventListener('click', startProcessing);

async function startProcessing() {
  if (!state.file || state.processing) return;
  state.processing = true;
  processBtn.disabled = true;

  // 1. Abre o player e começa a rodar o vídeo IMEDIATAMENTE
  state.localUrl = URL.createObjectURL(state.file);
  playerFileName.textContent = state.file.name;
  playerSection.classList.remove('hidden');
  uploadSection.classList.add('hidden');
  videoPlayer.src = state.localUrl;

  // O vídeo começa assim que as primeiras legendas ficarem prontas e nunca
  // passa do trecho já transcrito — assim a legenda permanece sincronizada.
  showOverlay('Processando o áudio…', 'O vídeo começa assim que as primeiras legendas ficarem prontas');
  setStatus('pending');
  setProgress(2, 'Enviando o vídeo…');

  // 2. Faz o upload e inicia o processamento no servidor
  try {
    const data = await uploadVideo(state.file);
    state.jobId = data.job_id;
    startPolling();
    showNotification('Vídeo enviado! A transcrição começou.', 'success');
  } catch (err) {
    state.processing = false;
    processBtn.disabled = false;
    uploadSection.classList.remove('hidden');
    setStatus('failed');
    setProgress(0, 'Erro no upload');
    showNotification(`Erro no upload: ${err.message}`, 'error');
  }
}

// -------- sobreposição do player (controle da reprodução) -----------------
function showOverlay(title, step, withPlayButton = false) {
  playerOverlayTitle.textContent = title;
  playerOverlayStep.textContent = step;
  overlaySpinner.classList.toggle('hidden', withPlayButton);
  overlayPlayBtn.classList.toggle('hidden', !withPlayButton);
  overlayPlayBtn.classList.toggle('inline-flex', withPlayButton);
  playerOverlay.classList.remove('hidden');
}

function hideOverlay() {
  playerOverlay.classList.add('hidden');
}

// Até onde já temos legenda (fim do último trecho transcrito).
function transcribedUntil() {
  let end = 0;
  for (const s of state.segments) if (s.end > end) end = s.end;
  return end;
}

// Libera a reprodução assim que existir o primeiro trecho transcrito.
async function tryStartPlayback() {
  if (state.playStarted) return;
  state.playStarted = true;
  try {
    await videoPlayer.play();
    hideOverlay();
  } catch (_) {
    // Autoplay bloqueado pelo navegador: o clique do usuário libera o som.
    showOverlay('Pronto para assistir', 'Clique em "Assistir com legendas" para começar', true);
  }
}

overlayPlayBtn.addEventListener('click', async () => {
  try {
    await videoPlayer.play();
    hideOverlay();
  } catch (_) {
    /* o usuário pode usar os controles do player */
  }
});

// Se o vídeo alcançar o fim do que já foi transcrito, pausa e espera.
function checkFrontier() {
  if (state.completed || !state.playStarted || videoPlayer.paused) return;
  const horizon = transcribedUntil();
  if (horizon > 0 && videoPlayer.currentTime >= horizon - 0.25) {
    videoPlayer.pause();
    state.waiting = true;
    showOverlay('Aguardando a transcrição…', 'O vídeo continua sozinho assim que os próximos trechos ficarem prontos');
  }
}

// Retoma a reprodução quando a transcrição avança além do ponto atual.
function resumeIfWaiting() {
  if (!state.waiting) return;
  const horizon = transcribedUntil();
  if (state.completed || horizon > videoPlayer.currentTime + 3) {
    state.waiting = false;
    hideOverlay();
    videoPlayer.play().catch(() => {});
  }
}

async function uploadVideo(file) {
  const formData = new FormData();
  formData.append('video_file', file);
  formData.append('language', languageSelect ? languageSelect.value : '');
  const response = await fetch('/api/upload/', {
    method: 'POST',
    body: formData,
    headers: { 'X-CSRFToken': csrftoken },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${response.status}`);
  }
  return response.json();
}

// ---------------------------------------------------------------- polling
function startPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(pollProgress, POLL_INTERVAL_MS);
  pollProgress();
}

function stopPolling() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

async function pollProgress() {
  if (!state.jobId) return;
  try {
    const response = await fetch(`/api/progress/${state.jobId}/`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    applyProgress(data);
  } catch (err) {
    console.error('Erro ao consultar progresso:', err);
  }
}

function applyProgress(data) {
  const status = data.status || 'pending';
  const info = STATUS[status] || {};
  let pct = data.progress_percentage || 0;
  if (status === 'completed') pct = 100;
  setProgress(pct, info.label || data.current_step || 'Processando…');
  setStatus(status);

  renderSegments(data.segments || []);

  updateLanguageBadge(data.language_label, status);

  state.files = data.files || {};

  if (status === 'completed') {
    state.completed = true;
    stopPolling();
    state.processing = false;
    processBtn.disabled = false;
    enableDownloads();
    showNotification('Transcrição concluída! Legendas disponíveis.', 'success');
    if (state.waiting) { state.waiting = false; hideOverlay(); }
    if (!state.playStarted) tryStartPlayback();
    else videoPlayer.play().catch(() => {});
  } else if (status === 'failed') {
    stopPolling();
    state.processing = false;
    processBtn.disabled = false;
    showNotification('O processamento falhou. Verifique o vídeo e tente novamente.', 'error');
    const motivo = (data.current_step || '').replace(/^Erro:\s*/i, '').trim();
    showOverlay('Não foi possível transcrever', motivo || 'Você ainda pode assistir ao vídeo, sem legendas.', true);
  } else {
    // Começa a tocar no primeiro trecho e retoma quando a transcrição avançar.
    if (!state.playStarted) {
      if ((data.segments || []).length > 0) tryStartPlayback();
      else playerOverlayStep.textContent = info.label || 'Processando…';
    }
    resumeIfWaiting();
  }
}

// ---------------------------------------------------------------- legenda
function updateLanguageBadge(label, status) {
  if (!languageBadge) return;
  label = (label || '').trim();
  if (label) {
    languageBadge.textContent = label;
    languageBadge.classList.remove('hidden');
  } else if (status === 'pending' || status === 'extracting' || status === 'transcribing') {
    languageBadge.textContent = 'Detectando idioma…';
    languageBadge.classList.remove('hidden');
  } else {
    languageBadge.classList.add('hidden');
  }
}

function renderSegments(segments) {
  if (!Array.isArray(segments)) return;

  for (let i = state.rendered; i < segments.length; i++) {
    const seg = segments[i];
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'segment is-new';
    btn.dataset.index = i;
    btn.dataset.start = seg.start;
    btn.dataset.end = seg.end;

    const time = document.createElement('span');
    time.className = 'segment-time';
    time.textContent = formatTime(seg.start);

    const text = document.createElement('span');
    text.className = 'segment-text';
    text.textContent = seg.text;

    btn.append(time, text);
    btn.addEventListener('click', () => seekTo(seg.start));
    transcriptList.appendChild(btn);

    state.elByIndex[i] = btn;
    state.rendered++;
    setTimeout(() => btn.classList.remove('is-new'), 350);
  }

  state.segments = segments;

  if (transcriptEmpty) transcriptEmpty.style.display = segments.length ? 'none' : 'flex';
  segmentCount.textContent = `${segments.length} trecho${segments.length === 1 ? '' : 's'}`;
}

function currentIndexForTime(t) {
  const segs = state.segments;
  let idx = -1;
  for (let i = 0; i < segs.length; i++) {
    if (segs[i].start <= t + 0.05) idx = i;
    else break;
  }
  return idx;
}

function setActive(idx) {
  if (idx === state.activeIndex) return;
  const prev = state.elByIndex[state.activeIndex];
  if (prev) prev.classList.remove('is-active');

  state.activeIndex = idx;
  const current = state.elByIndex[idx];

  if (current) {
    current.classList.add('is-active');
    if (state.subtitlesOn) {
      liveCaption.textContent = current.querySelector('.segment-text').textContent;
      liveCaption.classList.add('is-visible');
    }
    scrollSegmentIntoView(current);
  } else {
    liveCaption.classList.remove('is-visible');
  }
}

function scrollSegmentIntoView(node) {
  const viewTop = transcriptList.scrollTop;
  const viewBottom = viewTop + transcriptList.clientHeight;
  const nodeTop = node.offsetTop;
  const nodeBottom = nodeTop + node.offsetHeight;

  if (nodeTop < viewTop + 8) {
    transcriptList.scrollTo({ top: nodeTop - 8, behavior: 'smooth' });
  } else if (nodeBottom > viewBottom - 8) {
    transcriptList.scrollTo({ top: nodeBottom - transcriptList.clientHeight + 8, behavior: 'smooth' });
  }
}

function seekTo(seconds) {
  if (!Number.isFinite(seconds)) return;
  videoPlayer.currentTime = Math.max(0, seconds - 0.05);
  if (videoPlayer.paused) videoPlayer.play().catch(() => {});
}

videoPlayer.addEventListener('timeupdate', () => {
  setActive(currentIndexForTime(videoPlayer.currentTime));
  checkFrontier();
});

videoPlayer.addEventListener('seeking', () => {
  setActive(currentIndexForTime(videoPlayer.currentTime));
});

toggleSubtitles.addEventListener('click', () => {
  state.subtitlesOn = !state.subtitlesOn;
  toggleSubtitles.innerHTML = `<i class="fas fa-closed-captioning"></i> Legendas: ${state.subtitlesOn ? 'ligadas' : 'desligadas'}`;
  if (!state.subtitlesOn) {
    liveCaption.classList.remove('is-visible');
  } else {
    state.activeIndex = -99; // forca reavaliacao do trecho atual
    setActive(currentIndexForTime(videoPlayer.currentTime));
  }
});

el('newVideoBtn').addEventListener('click', resetApplication);

// ---------------------------------------------------------------- downloads
function enableDownloads() {
  downloadSection.classList.remove('hidden');
}
el('downloadVideo').addEventListener('click', () => downloadFile('video'));
el('downloadSrt').addEventListener('click', () => downloadFile('srt'));
el('downloadVtt').addEventListener('click', () => downloadFile('vtt'));
el('downloadTranscript').addEventListener('click', () => downloadFile('transcript'));

function downloadFile(type) {
  if (!state.jobId) return;
  const endpoints = {
    video: `/api/transcription/${state.jobId}/download_video/`,
    srt: `/api/transcription/${state.jobId}/download_srt/`,
    vtt: `/api/transcription/${state.jobId}/download_vtt/`,
    transcript: `/api/transcription/${state.jobId}/download_transcript/`,
  };
  const names = {
    video: 'video_com_legendas.mp4',
    srt: 'legendas.srt',
    vtt: 'legendas.vtt',
    transcript: 'transcricao.txt',
  };
  const link = document.createElement('a');
  link.href = endpoints[type];
  link.download = names[type];
  document.body.appendChild(link);
  link.click();
  link.remove();
  showNotification(`Baixando ${names[type]}…`, 'info');
}

// ---------------------------------------------------------------- reset
resetBtn.addEventListener('click', resetApplication);

function resetApplication() {
  stopPolling();
  if (state.localUrl) {
    URL.revokeObjectURL(state.localUrl);
    state.localUrl = null;
  }

  state.file = null;
  state.jobId = null;
  state.processing = false;
  state.playStarted = false;
  state.waiting = false;
  state.completed = false;
  state.rendered = 0;
  state.segments = [];
  state.elByIndex = [];
  state.activeIndex = -1;
  state.files = {};

  fileInput.value = '';
  processBtn.disabled = false;
  fileSelected.classList.add('hidden');
  fileSelected.classList.remove('flex');

  videoPlayer.pause();
  videoPlayer.removeAttribute('src');
  videoPlayer.load();

  transcriptList.querySelectorAll('.segment').forEach((n) => n.remove());
  if (transcriptEmpty) transcriptEmpty.style.display = 'flex';
  segmentCount.textContent = '0 trechos';
  if (languageBadge) languageBadge.classList.add('hidden');
  liveCaption.classList.remove('is-visible');
  liveCaption.textContent = '';

  playerSection.classList.add('hidden');
  downloadSection.classList.add('hidden');
  uploadSection.classList.remove('hidden');
  hideOverlay();

  setStatus('idle');
  statusText.textContent = 'Pronto';
  statusDot.style.backgroundColor = '#64748b';
  setProgress(0, 'Aguardando upload…');
}

// reinicia o estado visual ao carregar
document.addEventListener('DOMContentLoaded', () => {
  setProgress(0, 'Aguardando upload…');
});
