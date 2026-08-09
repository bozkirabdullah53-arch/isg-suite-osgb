import {api} from './api';

const BUTTON_ATTR = 'data-eisa-orphan-cleanup';
const LEGACY_STATUS_PREFILL = 'hekimbir@gmail.com';
let observer = null;
let timer = null;

function findEmailInput() {
  const labels = Array.from(document.querySelectorAll('label'));
  const label = labels.find((node) => String(node.textContent || '').includes('Kullanıcı e-postası'));
  return label?.querySelector('input') || null;
}

function clearLegacyStatusPrefill() {
  const emailInput = findEmailInput();
  if (!emailInput) return;

  emailInput.setAttribute('autocomplete', 'off');
  emailInput.setAttribute('autocapitalize', 'none');
  emailInput.setAttribute('spellcheck', 'false');
  emailInput.setAttribute('data-lpignore', 'true');

  if (emailInput.dataset.eisaLegacyPrefillChecked === '1') return;
  emailInput.dataset.eisaLegacyPrefillChecked = '1';

  const current = String(emailInput.value || '').trim().toLowerCase();
  if (current !== LEGACY_STATUS_PREFILL) return;

  const valueSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  if (valueSetter) valueSetter.call(emailInput, '');
  else emailInput.value = '';

  emailInput.dispatchEvent(new Event('input', {bubbles: true}));
  emailInput.dispatchEvent(new Event('change', {bubbles: true}));
}

function orphanCardFromStatusText(node) {
  let current = node?.parentElement || null;
  while (current && current !== document.body) {
    const text = String(current.textContent || '');
    if (
      text.includes('Bağlantı durumu:') &&
      text.includes('Eksik / yetim hesap') &&
      text.includes('Durum:') &&
      text.includes('Pasif') &&
      text.includes('Hesap Kilidini Kaldır')
    ) return current;
    current = current.parentElement;
  }
  return null;
}

async function cleanup(button) {
  const emailInput = findEmailInput();
  const email = String(emailInput?.value || '').trim().toLowerCase();
  if (!email) {
    window.alert('Önce yetim hesabın e-posta adresini bulun.');
    return;
  }
  if (!window.confirm(
    `"${email}" yetim hesabı kalıcı olarak temizlensin mi?\n\n` +
    'Bu işlem hesabın kişisel kimliğini ve giriş bilgilerini geri döndürülemez biçimde kaldırır. ' +
    'Audit/geçmiş kayıtların referans bütünlüğü korunur ve aynı e-posta yeniden kullanılabilir.'
  )) return;

  const original = button.textContent;
  button.disabled = true;
  button.textContent = 'Temizleniyor…';
  try {
    const result = await api('/eisa/users/cleanup-orphan', {
      method: 'POST',
      body: JSON.stringify({email}),
    });
    window.alert(result?.message || 'Yetim hesap temizlendi.');
    window.location.reload();
  } catch (error) {
    window.alert(String(error?.message || error || 'Yetim hesap temizlenemedi.'));
    button.disabled = false;
    button.textContent = original;
  }
}

function attach() {
  clearLegacyStatusPrefill();

  const statusNodes = Array.from(document.querySelectorAll('p')).filter((node) => {
    const text = String(node.textContent || '');
    return text.includes('Bağlantı durumu:') && text.includes('Eksik / yetim hesap');
  });

  for (const statusNode of statusNodes) {
    const card = orphanCardFromStatusText(statusNode);
    if (!card || card.querySelector(`[${BUTTON_ATTR}]`)) continue;
    card.setAttribute('data-eisa-orphan-card', '');
    const lockButton = Array.from(card.querySelectorAll('button')).find(
      (node) => String(node.textContent || '').includes('Hesap Kilidini Kaldır'),
    );
    const actions = lockButton?.parentElement;
    if (!actions) continue;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'secondary';
    button.setAttribute(BUTTON_ATTR, '');
    button.style.borderColor = '#dc2626';
    button.style.color = '#b91c1c';
    button.textContent = 'Yetim Hesabı Kalıcı Temizle';
    button.title = 'Yalnız pasif ve hiçbir OSGB/işyeri/profesyonel/üyelik bağı kalmamış hesaplarda çalışır.';
    button.addEventListener('click', () => void cleanup(button));
    actions.appendChild(button);
  }
}

function scheduleAttach() {
  if (timer) return;
  timer = window.setTimeout(() => {
    timer = null;
    attach();
  }, 120);
}

observer = new MutationObserver(scheduleAttach);
observer.observe(document.documentElement, {childList: true, subtree: true});
scheduleAttach();

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    observer?.disconnect();
    if (timer) window.clearTimeout(timer);
  });
}
