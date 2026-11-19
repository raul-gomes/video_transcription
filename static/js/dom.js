/**
 * Tiny DOM builder. Text always goes through textContent, never innerHTML,
 * so data from the API can't inject markup (ADR 0006).
 */

/**
 * Create an element.
 * @param {string} tag
 * @param {Object<string, any>} [attrs]  `class`, `text`, `on<Event>` handlers,
 *   boolean attributes (`disabled`, `hidden`) and any other attribute.
 * @param {(Node|string|null|undefined|false)[]} [children]
 * @returns {HTMLElement}
 */
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (value === true) node.setAttribute(key, '');
    else node.setAttribute(key, String(value));
  }
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

/**
 * Font Awesome icon.
 * @param {string} name  Icon name without the `fa-` prefix.
 * @returns {HTMLElement}
 */
export function icon(name) {
  return el('i', { class: `fas fa-${name}`, 'aria-hidden': 'true' });
}

/**
 * Format seconds as m:ss or h:mm:ss.
 * @param {number|null} seconds
 * @returns {string}
 */
export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return '';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, '0');
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

/**
 * Format bytes in MB/GB, pt-BR.
 * @param {number} bytes
 * @returns {string}
 */
export function formatSize(bytes) {
  const mb = bytes / (1024 * 1024);
  return mb >= 1024
    ? `${(mb / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} GB`
    : `${mb.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`;
}

/**
 * Format an ISO date for the history list.
 * @param {string} iso
 * @returns {string}
 */
export function formatDate(iso) {
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}
