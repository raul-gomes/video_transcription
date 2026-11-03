/* ==========================================================================
   Biblioteca — lista os vídeos enviados e atualiza o progresso ao vivo
   ========================================================================== */

const STATUS_STYLE = {
  pending:      'border-slate-400/30 bg-slate-400/10 text-slate-300',
  extracting:   'border-amber-400/30 bg-amber-400/10 text-amber-300',
  transcribing: 'border-brand-400/30 bg-brand-400/10 text-brand-300',
  generating:   'border-amber-400/30 bg-amber-400/10 text-amber-300',
  completed:    'border-emerald-400/30 bg-emerald-400/10 text-emerald-300',
  failed:       'border-rose-400/30 bg-rose-400/10 text-rose-300',
};

const BADGE_BASE = 'shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-medium ';

const grid = document.getElementById('jobGrid');
const libCount = document.getElementById('libCount');
let timer = null;

function applyCard(card, job) {
  const bar   = card.querySelector('[data-bar]');
  const pct   = card.querySelector('[data-pct]');
  const step  = card.querySelector('[data-step]');
  const seg   = card.querySelector('[data-segments]');
  const badge = card.querySelector('[data-status]');
  const langWrap = card.querySelector('[data-language-wrap]');
  const lang  = card.querySelector('[data-language]');

  const value = job.status === 'completed' ? 100 : (job.progress || 0);
  if (bar) bar.style.width = `${value}%`;
  if (pct) pct.textContent = `${value}%`;
  if (step) step.textContent = job.current_step || job.status_label || '';
  if (seg) seg.textContent = `${job.segments} trecho${job.segments === 1 ? '' : 's'}`;
  if (lang) lang.textContent = job.language_label || '';
  if (langWrap) langWrap.classList.toggle('hidden', !job.language_label);
  if (badge) {
    badge.className = BADGE_BASE + (STATUS_STYLE[job.status] || 'border-white/15 bg-white/5 text-slate-300');
    badge.textContent = job.status_label || job.status;
  }
}

async function refresh() {
  try {
    const res = await fetch('/api/jobs/');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const jobs = await res.json();

    // Se a quantidade mudou (novo upload/remoção), recarrega a página inteira.
    if (jobs.length !== window.JOB_COUNT) {
      location.reload();
      return;
    }

    jobs.forEach((job) => {
      const card = grid && grid.querySelector(`.job-card[data-id="${job.id}"]`);
      if (card) applyCard(card, job);
    });

    if (libCount) libCount.textContent = `${jobs.length} vídeo${jobs.length === 1 ? '' : 's'}`;

    // Quando nada mais está processando, para de consultar o servidor.
    if (!jobs.some((j) => j.active)) stop();
  } catch (err) {
    console.error('Falha ao atualizar a lista de vídeos:', err);
  }
}

function stop() {
  if (timer) { clearInterval(timer); timer = null; }
}

function start() {
  stop();
  timer = setInterval(refresh, 3000);
}

// Estado inicial: colore os selos já renderizados pelo servidor.
document.querySelectorAll('.job-card[data-id]').forEach((card) => {
  const badge = card.querySelector('[data-status]');
  const s = badge && badge.dataset.status;
  if (badge && STATUS_STYLE[s]) badge.className = BADGE_BASE + STATUS_STYLE[s];
});

start();
refresh();

document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refresh();
});
