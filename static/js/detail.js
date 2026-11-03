/* ==========================================================================
   Detalhe do vídeo — player + legenda sincronizada (a partir de uma lista)
   ========================================================================== */

const POLL_INTERVAL_MS = 2000;
const JOB_ID = window.JOB_ID;
const POS_KEY = `vt_pos_${JOB_ID}`;   // guarda a posição de onde o usuário parou

const el = (id) => document.getElementById(id);

const videoPlayer     = el('videoPlayer');
const liveCaption     = el('liveCaption');
const toggleSubtitles = el('toggleSubtitles');

const playerOverlay      = el('playerOverlay');
const overlaySpinner     = el('overlaySpinner');
const overlayPlayBtn     = el('overlayPlayBtn');
const playerOverlayTitle = el('playerOverlayTitle');
const playerOverlayStep  = el('playerOverlayStep');

const downloadSection = el('downloadSection');
const progressFill    = el('progressFill');
const progressLabel   = el('progressLabel');
const progressPercent = el('progressPercent');
const statusText      = el('statusText');
const statusDot       = el('statusDot');

const transcriptList  = el('transcriptList');
const transcriptEmpty = el('transcriptEmpty');
const segmentCount    = el('segmentCount');
const languageBadge   = el('languageBadge');

const notification     = el('notification');
const notificationText = el('notificationText');
const notificationIcon = el('notificationIcon');

const state = {
  rendered: 0,
  segments: [],
  elByIndex: [],
  activeIndex: -1,
  subtitlesOn: true,
  srcSet: false,
  playStarted: false,
  waiting: false,
  completed: false,
  resumeTarget: 0,
  timer: null,
};

const STATUS = {
  pending:      { label: 'Na fila de processamento…', short: 'Na fila',           color: '#94a3b8' },
  extracting:   { label: 'Extraindo o áudio do vídeo…', short: 'Extraindo áudio',  color: '#fbbf24' },
  transcribing: { label: 'Transcrevendo com Whisper…', short: 'Transcrevendo',     color: '#3fadbd' },
  generating:   { label: 'Gerando arquivos de legenda…', short: 'Gerando legendas', color: '#fbbf24' },
  completed:    { label: 'Processamento concluído!', short: 'Concluído',           color: '#34d399' },
  failed:       { label: 'Falha no processamento', short: 'Erro',                  color: '#f87171' },
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

function showNotification(message, type = 'info') {
  notificationText.textContent = message;
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

// ---------------------------------------------------- sobreposição do player
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

  // Posiciona o vídeo: usa a posição salva, mas se ela ainda não foi
  // transcrita, começa do trecho já disponível.
  const horizon = transcribedUntil();
  let target = state.resumeTarget || 0;
  if (videoPlayer.duration && target >= videoPlayer.duration - 1) target = 0;
  if (target > 0 && horizon > 0 && target > horizon) {
    target = Math.max(0, horizon - 2);
    showNotification('A transcrição ainda não chegou onde você parou — começando do trecho já pronto.', 'info');
  } else if (target > 0) {
    showNotification(`Retomando de ${formatTime(target)}…`, 'info');
  }
  if (target > 0) seekWhenReady(target);

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

// ---------------------------------------------------------------- polling
function startPolling() {
  if (state.timer) clearInterval(state.timer);
  state.timer = setInterval(pollProgress, POLL_INTERVAL_MS);
  pollProgress();
}

function stopPolling() {
  if (state.timer) { clearInterval(state.timer); state.timer = null; }
}

async function pollProgress() {
  if (!JOB_ID) return;
  try {
    const response = await fetch(`/api/progress/${JOB_ID}/`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    applyProgress(await response.json());
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

  // Define a fonte do vídeo uma única vez (o vídeo original enviado).
  if (!state.srcSet && data.video_url) {
    videoPlayer.src = data.video_url;
    state.srcSet = true;
  }

  renderSegments(data.segments || []);

  updateLanguageBadge(data.language_label, status);

  if (status === 'completed') {
    state.completed = true;
    stopPolling();
    enableDownloads();
    if (state.waiting) { state.waiting = false; hideOverlay(); }
    if (!state.playStarted) tryStartPlayback();
    else videoPlayer.play().catch(() => {});
  } else if (status === 'failed') {
    stopPolling();
    showNotification('O processamento falhou. Verifique o vídeo e tente novamente.', 'error');
    const motivo = (data.current_step || '').replace(/^Erro:\s*/i, '').trim();
    showOverlay('Não foi possível transcrever', motivo || 'Você ainda pode assistir ao vídeo, sem legendas.', true);
  } else {
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
  savePosition();
});

videoPlayer.addEventListener('seeking', () => {
  setActive(currentIndexForTime(videoPlayer.currentTime));
});

// -------- retomar de onde parou --------------------------------------------
let lastSaved = 0;

function savePosition() {
  const t = videoPlayer.currentTime;
  if (Math.abs(t - lastSaved) < 3) return;
  lastSaved = t;
  try { localStorage.setItem(POS_KEY, String(t)); } catch (_) { /* modo privado */ }
}

// Lê a posição salva imediatamente (aplicada quando iniciarmos a reprodução).
try { state.resumeTarget = parseFloat(localStorage.getItem(POS_KEY) || '0') || 0; } catch (_) { state.resumeTarget = 0; }

function seekWhenReady(time) {
  if (videoPlayer.readyState >= 1) {
    videoPlayer.currentTime = time;
  } else {
    videoPlayer.addEventListener('loadedmetadata', () => { videoPlayer.currentTime = time; }, { once: true });
  }
}

toggleSubtitles.addEventListener('click', () => {
  state.subtitlesOn = !state.subtitlesOn;
  toggleSubtitles.innerHTML = `<i class="fas fa-closed-captioning"></i> Legendas: ${state.subtitlesOn ? 'ligadas' : 'desligadas'}`;
  if (!state.subtitlesOn) {
    liveCaption.classList.remove('is-visible');
  } else {
    state.activeIndex = -99;
    setActive(currentIndexForTime(videoPlayer.currentTime));
  }
});

// ---------------------------------------------------------------- downloads
function enableDownloads() {
  downloadSection.classList.remove('hidden');
}
el('downloadVideo').addEventListener('click', () => downloadFile('video'));
el('downloadSrt').addEventListener('click', () => downloadFile('srt'));
el('downloadVtt').addEventListener('click', () => downloadFile('vtt'));
el('downloadTranscript').addEventListener('click', () => downloadFile('transcript'));

function downloadFile(type) {
  if (!JOB_ID) return;
  const endpoints = {
    video: `/api/transcription/${JOB_ID}/download_video/`,
    srt: `/api/transcription/${JOB_ID}/download_srt/`,
    vtt: `/api/transcription/${JOB_ID}/download_vtt/`,
    transcript: `/api/transcription/${JOB_ID}/download_transcript/`,
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

// ---------------------------------------------------------------- início
showOverlay('Carregando o vídeo…', 'Aguarde um instante');
startPolling();
