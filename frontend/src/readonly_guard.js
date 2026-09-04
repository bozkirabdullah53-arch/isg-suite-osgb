const READ_ONLY_MARKERS = [
  'Salt okunur mod: abonelik süresi doldu',
  'Abonelik süresi doldu veya askıda',
  'Veri girişi kapalı',
];

const WRITE_BUTTON_RE = /^(firma ekle|işyeri ekle|profesyonel ekle|i̇sg profesyoneli ekle|görevlendirme ekle|kaydet|sil|pasife al|aktife al|aktifleştir|onayla|reddet|gönder|yükle|defter kaydı)$/i;

function isReadOnlyPage() {
  const text = document.body?.innerText || '';
  return READ_ONLY_MARKERS.some((marker) => text.includes(marker));
}

function setDisabled(el, disabled) {
  if (!(el instanceof HTMLElement)) return;
  if (disabled) {
    if (!el.dataset.subscriptionReadonly) {
      el.dataset.subscriptionReadonly = '1';
      el.dataset.subscriptionWasDisabled = el.disabled ? '1' : '0';
    }
    el.disabled = true;
    el.setAttribute('aria-disabled', 'true');
    el.title = 'Abonelik askıda veya süresi dolmuş. Salt okunur mod.';
  } else if (el.dataset.subscriptionReadonly === '1') {
    if (el.dataset.subscriptionWasDisabled !== '1') el.disabled = false;
    el.removeAttribute('aria-disabled');
    delete el.dataset.subscriptionReadonly;
    delete el.dataset.subscriptionWasDisabled;
  }
}

/** Convert the legacy third-party QR URL to our same-origin renderer. */
function rewriteQrSrc(value) {
  const src = String(value || '');
  if (!src) return src;
  try {
    const url = new URL(src, window.location.href);
    if (url.hostname !== 'api.qrserver.com') return src;
    const data = url.searchParams.get('data');
    if (!data) return src;
    const local = new URL('/api/v1/companies/qr-render', window.location.origin);
    local.searchParams.set('data', data);
    return local.toString();
  } catch {
    return src;
  }
}

/**
 * React normally assigns <img src> through the DOM property. Rewrite QR-server
 * URLs at assignment time so the browser never needs to fetch the third-party
 * URL. MutationObserver remains as a fallback.
 */
(function installQrRewriteHooks() {
  try {
    const imageProto = HTMLImageElement.prototype;
    const srcDescriptor = Object.getOwnPropertyDescriptor(imageProto, 'src');
    if (srcDescriptor?.set && srcDescriptor.get) {
      Object.defineProperty(imageProto, 'src', {
        configurable: srcDescriptor.configurable,
        enumerable: srcDescriptor.enumerable,
        get() { return srcDescriptor.get.call(this); },
        set(value) { srcDescriptor.set.call(this, rewriteQrSrc(value)); },
      });
    }
    const originalSetAttribute = imageProto.setAttribute;
    imageProto.setAttribute = function setAttribute(name, value) {
      if (String(name).toLowerCase() === 'src') {
        return originalSetAttribute.call(this, name, rewriteQrSrc(value));
      }
      return originalSetAttribute.call(this, name, value);
    };
  } catch {
    // Fallback observer below remains active.
  }
})();

function normalizeQrImage(el) {
  if (!(el instanceof HTMLImageElement)) return;
  const src = String(el.getAttribute('src') || el.src || '');
  const localSrc = rewriteQrSrc(src);
  if (localSrc && localSrc !== src) {
    try { el.setAttribute('src', localSrc); } catch { el.src = localSrc; }
  }
}

function normalizeExistingQrImages(root = document) {
  root.querySelectorAll?.('img').forEach(normalizeQrImage);
}

function applyReadOnlyGuard() {
  const blocked = isReadOnlyPage();
  document.documentElement.classList.toggle('subscription-readonly', blocked);
  document.querySelectorAll('button').forEach((button) => {
    const label = (button.innerText || button.textContent || '').trim().replace(/\s+/g, ' ');
    if (WRITE_BUTTON_RE.test(label) || /\b(Ekle|Kaydet|Sil|Gönder|Yükle)\b/i.test(label)) {
      setDisabled(button, blocked);
    }
  });
  document.querySelectorAll('.modal, [role="dialog"]').forEach((modal) => {
    const warning = modal.innerText || '';
    if (!blocked && !READ_ONLY_MARKERS.some((marker) => warning.includes(marker))) return;
    modal.querySelectorAll('input, select, textarea, button[type="submit"]').forEach((el) => setDisabled(el, true));
  });
  normalizeExistingQrImages();
}

let scheduled = false;
function scheduleGuard() {
  if (scheduled) return;
  scheduled = true;
  queueMicrotask(() => {
    scheduled = false;
    applyReadOnlyGuard();
  });
}

document.addEventListener('DOMContentLoaded', scheduleGuard);
window.addEventListener('hashchange', scheduleGuard);
new MutationObserver(scheduleGuard).observe(document.documentElement, {
  childList: true,
  subtree: true,
  characterData: true,
});

new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    if (mutation.type === 'attributes' && mutation.target instanceof HTMLImageElement) {
      normalizeQrImage(mutation.target);
    }
  }
}).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ['src'],
  subtree: true,
});

document.addEventListener('submit', (event) => {
  if (!isReadOnlyPage()) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}, true);

scheduleGuard();
