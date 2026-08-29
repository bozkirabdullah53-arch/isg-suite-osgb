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

function clearLoginUsernamePlaceholder() {
  const input = document.querySelector('.login-card input[autocomplete="username"]');
  if (input?.hasAttribute('placeholder')) input.removeAttribute('placeholder');
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

function applyReadOnlyGuard() {
  clearLoginUsernamePlaceholder();
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

document.addEventListener('submit', (event) => {
  if (!isReadOnlyPage()) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}, true);

scheduleGuard();
