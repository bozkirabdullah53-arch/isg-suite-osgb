import {api} from './api';
import {getAccessToken} from './auth_session';
import {isWorkplaceManagerUser} from './workplace_user_policy';

const READ_ONLY_MARKERS = [
  'Salt okunur mod: abonelik süresi doldu',
  'Abonelik süresi doldu veya askıda',
  'Veri girişi kapalı',
];

const WORKPLACE_READONLY_TITLES = new Set([
  'İşyeri Denetim Durumu',
  'Eğitim Kayıtları',
  'Dokümanlar',
  'Çalışan Sağlık Kartları',
]);

const WRITE_BUTTON_RE = /^(firma ekle|işyeri ekle|profesyonel ekle|i̇sg profesyoneli ekle|görevlendirme ekle|kaydet|sil|pasife al|aktife al|aktifleştir|onayla|reddet|gönder|yükle|defter kaydı)$/i;

function isSubscriptionReadOnlyPage() {
  const text = document.body?.innerText || '';
  return READ_ONLY_MARKERS.some((marker) => text.includes(marker));
}

function activePageTitle() {
  return (document.querySelector('.page-title h3')?.textContent || '').trim().replace(/\s+/g, ' ');
}

let userToken = '';
let currentUserPromise = null;
async function currentUser() {
  const token = getAccessToken() || '';
  if (!token) {
    userToken = '';
    currentUserPromise = null;
    return null;
  }
  if (token !== userToken) {
    userToken = token;
    currentUserPromise = api('/auth/me').catch(() => null);
  }
  return currentUserPromise;
}

async function isWorkplaceModuleReadOnlyPage() {
  const title = activePageTitle();
  if (!WORKPLACE_READONLY_TITLES.has(title)) return false;
  return isWorkplaceManagerUser(await currentUser());
}

function setDisabled(el, disabled, reason = '') {
  if (!(el instanceof HTMLElement)) return;
  if (disabled) {
    if (!el.dataset.subscriptionReadonly) {
      el.dataset.subscriptionReadonly = '1';
      el.dataset.subscriptionWasDisabled = el.disabled ? '1' : '0';
    }
    el.disabled = true;
    el.setAttribute('aria-disabled', 'true');
    el.title = reason || 'Salt okunur mod.';
  } else if (el.dataset.subscriptionReadonly === '1') {
    if (el.dataset.subscriptionWasDisabled !== '1') el.disabled = false;
    el.removeAttribute('aria-disabled');
    el.removeAttribute('title');
    delete el.dataset.subscriptionReadonly;
    delete el.dataset.subscriptionWasDisabled;
  }
}

function guardControls(blocked, reason) {
  document.querySelectorAll('button').forEach((button) => {
    const label = (button.innerText || button.textContent || '').trim().replace(/\s+/g, ' ');
    if (WRITE_BUTTON_RE.test(label) || /\b(Ekle|Kaydet|Sil|Gönder|Yükle)\b/i.test(label)) {
      setDisabled(button, blocked, reason);
    }
  });

  document.querySelectorAll('.modal, [role="dialog"]').forEach((modal) => {
    const warning = modal.innerText || '';
    const modalBlocked = blocked || READ_ONLY_MARKERS.some((marker) => warning.includes(marker));
    modal.querySelectorAll('input, select, textarea, button[type="submit"]').forEach((el) => {
      setDisabled(el, modalBlocked, reason);
    });
  });
}

async function applyReadOnlyGuard() {
  const subscriptionBlocked = isSubscriptionReadOnlyPage();
  const workplaceBlocked = !subscriptionBlocked && await isWorkplaceModuleReadOnlyPage();
  const blocked = subscriptionBlocked || workplaceBlocked;
  const reason = subscriptionBlocked
    ? 'Abonelik askıda veya süresi dolmuş. Salt okunur mod.'
    : workplaceBlocked
      ? 'Bu modül işyeri hesabında sadece görüntülenebilir.'
      : '';

  document.documentElement.classList.toggle('subscription-readonly', subscriptionBlocked);
  document.documentElement.classList.toggle('workplace-module-readonly', workplaceBlocked);
  guardControls(blocked, reason);
}

let scheduled = false;
function scheduleGuard() {
  if (scheduled) return;
  scheduled = true;
  queueMicrotask(async () => {
    scheduled = false;
    await applyReadOnlyGuard();
  });
}

document.addEventListener('DOMContentLoaded', scheduleGuard);
window.addEventListener('hashchange', scheduleGuard);
new MutationObserver(scheduleGuard).observe(document.documentElement, {
  childList: true,
  subtree: true,
  characterData: true,
});

document.addEventListener('submit', async (event) => {
  const blocked = isSubscriptionReadOnlyPage() || await isWorkplaceModuleReadOnlyPage();
  if (!blocked) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}, true);

scheduleGuard();
