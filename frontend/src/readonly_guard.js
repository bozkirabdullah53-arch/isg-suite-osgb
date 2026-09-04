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

/**
 * Render legacy QR-server images through the ISG Suite API itself.
 * The QR endpoint is deliberately public and only receives the encoded payload;
 * using the direct API origin avoids dependence on the static-site proxy.
 */
const QR_API_ORIGIN = (() => {
  try {
    const host = String(window.location.hostname || '').toLowerCase();
    if (host === 'localhost' || host === '127.0.0.1') return window.location.origin;
  } catch {
    /* ignore */
  }
  return 'https://isg-suite-api-1u9t.onrender.com';
})();

function rewriteQrSrc(value) {
  const src = String(value || '');
  if (!src) return src;
  try {
    const url = new URL(src, window.location.href);
    if (url.hostname !== 'api.qrserver.com') return src;
    const data = url.searchParams.get('data');
    if (!data) return src;
    const local = new URL('/api/v1/companies/qr-render', QR_API_ORIGIN);
    local.searchParams.set('data', data);
    return local.toString();
  } catch {
    return src;
  }
}

/**
 * React may assign img.src as a DOM property. Rewrite it before the browser
 * starts the network request so the third-party QR service is never contacted.
 */
(function installQrSrcHook() {
  try {
    const proto = HTMLImageElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, 'src');
    if (descriptor?.set && descriptor?.get) {
      Object.defineProperty(proto, 'src', {
        configurable: descriptor.configurable,
        enumerable: descriptor.enumerable,
        get() {
          return descriptor.get.call(this);
        },
        set(value) {
          descriptor.set.call(this, rewriteQrSrc(value));
        },
      });
    }

    const originalSetAttribute = proto.setAttribute;
    proto.setAttribute = function setAttribute(name, value) {
      if (String(name).toLowerCase() === 'src') {
        return originalSetAttribute.call(this, name, rewriteQrSrc(value));
      }
      return originalSetAttribute.call(this, name, value);
    };
  } catch {
    // DOM observer below remains as a fallback.
  }
})();

function normalizeQrImage(el) {
  if (!(el instanceof HTMLImageElement)) return;
  const current = String(el.getAttribute('src') || el.src || '');
  const rewritten = rewriteQrSrc(current);
  if (!rewritten || rewritten === current) return;
  try {
    el.setAttribute('src', rewritten);
  } catch {
    el.src = rewritten;
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

const qrRescanTimer = window.setInterval(() => normalizeExistingQrImages(), 300);
window.setTimeout(() => window.clearInterval(qrRescanTimer), 15000);

document.addEventListener('error', (event) => {
  const target = event.target;
  if (target instanceof HTMLImageElement) normalizeQrImage(target);
}, true);

document.addEventListener('submit', (event) => {
  if (!isReadOnlyPage()) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}, true);

scheduleGuard();
