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

/** Replace legacy third-party QR image URLs with same-origin API rendering. */
function normalizeQrImage(el) {
  if (!(el instanceof HTMLImageElement)) return;
  const src = String(el.getAttribute('src') || el.src || '');
  if (!src) return;
  try {
    const url = new URL(src, window.location.href);
    if (url.hostname !== 'api.qrserver.com') return;
    const data = url.searchParams.get('data');
    if (!data) return;
    const local = new URL('/api/v1/companies/qr-render', window.location.origin);
    local.searchParams.set('data', data);
    const localSrc = local.toString();
    if (el.src !== localSrc) el.src = localSrc;
  } catch {
    // Ignore malformed/non-QR image URLs.
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

// React may set image src after the DOM mutation callback; watch src attributes too.
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
