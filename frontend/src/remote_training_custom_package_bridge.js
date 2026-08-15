import {api} from './api';

const TRIGGER_ATTR = 'data-remote-custom-package-trigger';
const DIALOG_ATTR = 'data-remote-custom-package-dialog';
const STYLE_ID = 'remote-custom-package-bridge-style';

const SUPPORTED_SECTOR_CODES = new Set([
  'common',
  'construction',
  'battery',
  'metal',
  'logistics',
  'food',
  'chemical',
  'mining',
  'road',
  'office',
  'working_at_height',
]);

const FALLBACK_SECTORS = [
  {code: 'common', label: 'Temel Ortak İSG'},
  {code: 'construction', label: 'İnşaat'},
  {code: 'battery', label: 'Akü ve Otomotiv'},
  {code: 'metal', label: 'Metal'},
  {code: 'logistics', label: 'Lojistik'},
  {code: 'food', label: 'Gıda'},
  {code: 'chemical', label: 'Kimyasal/Boya'},
  {code: 'mining', label: 'Maden/Agrega'},
  {code: 'road', label: 'Yol/Asfalt/Altyapı'},
  {code: 'office', label: 'Ofis/Genel İşyerleri'},
  {code: 'working_at_height', label: 'Yüksekte Çalışma'},
];

let permissionPromise = null;
let canCreatePackage = false;
let injectionPending = false;

function ensureStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    .remote-custom-package-trigger {
      min-height: 40px;
      padding: 9px 14px;
      border: 1px solid #0f766e;
      border-radius: 8px;
      background: #0f766e;
      color: #fff;
      font-weight: 800;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(15, 118, 110, .16);
    }
    .remote-custom-package-trigger:hover { background: #0b5f59; }
    .remote-custom-package-overlay {
      position: fixed;
      inset: 0;
      z-index: 10050;
      display: grid;
      place-items: center;
      padding: 22px;
      background: rgba(8, 25, 39, .56);
      backdrop-filter: blur(2px);
    }
    .remote-custom-package-dialog {
      width: min(640px, 96vw);
      max-height: 92vh;
      overflow: auto;
      border-radius: 16px;
      background: #fff;
      box-shadow: 0 24px 70px rgba(7, 30, 48, .28);
      border: 1px solid #dbe5ef;
    }
    .remote-custom-package-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      padding: 20px 22px 14px;
      border-bottom: 1px solid #e6edf3;
    }
    .remote-custom-package-head h3 { margin: 0; color: #173b57; font-size: 21px; }
    .remote-custom-package-head p { margin: 6px 0 0; color: #5e7485; font-size: 13px; line-height: 1.45; }
    .remote-custom-package-close {
      border: 0;
      background: transparent;
      color: #496174;
      font-size: 26px;
      line-height: 1;
      cursor: pointer;
      padding: 2px 5px;
    }
    .remote-custom-package-body { padding: 20px 22px 22px; }
    .remote-custom-package-field { display: block; margin-bottom: 15px; }
    .remote-custom-package-field > span {
      display: block;
      margin-bottom: 6px;
      color: #24465f;
      font-weight: 750;
      font-size: 13px;
    }
    .remote-custom-package-field input,
    .remote-custom-package-field select,
    .remote-custom-package-field textarea {
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #bfd0dc;
      border-radius: 9px;
      padding: 10px 11px;
      background: #fff;
      color: #173b57;
      font: inherit;
    }
    .remote-custom-package-field textarea { min-height: 96px; resize: vertical; }
    .remote-custom-package-rules {
      margin: 4px 0 16px;
      padding: 12px 13px;
      border-radius: 10px;
      background: #effcfc;
      color: #36556d;
      font-size: 12px;
      line-height: 1.55;
    }
    .remote-custom-package-rules strong { color: #0f766e; }
    .remote-custom-package-error {
      display: none;
      margin: 0 0 14px;
      padding: 10px 12px;
      border-radius: 9px;
      background: #fff2f0;
      color: #b42318;
      font-size: 12px;
      font-weight: 700;
    }
    .remote-custom-package-actions {
      display: flex;
      justify-content: flex-end;
      gap: 9px;
      flex-wrap: wrap;
    }
    .remote-custom-package-actions button {
      min-height: 40px;
      padding: 9px 14px;
      border-radius: 8px;
      border: 1px solid #bfd0dc;
      background: #fff;
      color: #24465f;
      font-weight: 750;
      cursor: pointer;
    }
    .remote-custom-package-actions .primary {
      border-color: #0f766e;
      background: #0f766e;
      color: #fff;
    }
    .remote-custom-package-actions button:disabled {
      opacity: .65;
      cursor: wait;
    }
    .remote-custom-package-toast {
      position: fixed;
      z-index: 10080;
      right: 22px;
      bottom: 22px;
      max-width: min(460px, 90vw);
      padding: 13px 15px;
      border-radius: 10px;
      background: #0f766e;
      color: #fff;
      box-shadow: 0 12px 34px rgba(8, 40, 55, .24);
      font-size: 13px;
      font-weight: 700;
    }
  `;
  document.head.appendChild(style);
}

async function resolvePermission() {
  if (!permissionPromise) {
    permissionPromise = api('/auth/me', {_retries: 1})
      .then((user) => {
        canCreatePackage = Boolean(
          user?.role === 'company_admin'
          && Number(user?.osgb_id || 0) > 0
          && !user?.company_id,
        );
        return canCreatePackage;
      })
      .catch(() => {
        canCreatePackage = false;
        return false;
      });
  }
  return permissionPromise;
}

function findCatalogSection() {
  return [...document.querySelectorAll('section')].find((section) => {
    const text = section.textContent || '';
    return text.includes('Uzaktan Eğitim Paket Kataloğu')
      && text.includes('Paketleri yenile');
  }) || null;
}

function findRefreshButton(section = findCatalogSection()) {
  if (!section) return null;
  return [...section.querySelectorAll('button')].find(
    (button) => button.textContent?.trim() === 'Paketleri yenile',
  ) || null;
}

function closeDialog() {
  document.querySelector(`[${DIALOG_ATTR}]`)?.remove();
  document.body.style.removeProperty('overflow');
}

function showToast(message) {
  document.querySelector('.remote-custom-package-toast')?.remove();
  const toast = document.createElement('div');
  toast.className = 'remote-custom-package-toast';
  toast.setAttribute('role', 'status');
  toast.textContent = message;
  document.body.appendChild(toast);
  window.setTimeout(() => toast.remove(), 5200);
}

function focusCreatedPackage(title) {
  let attempts = 0;
  const timer = window.setInterval(() => {
    attempts += 1;
    const section = findCatalogSection();
    const target = section
      ? [...section.querySelectorAll('button')].find((button) => {
          const strong = button.querySelector('strong');
          return strong?.textContent?.trim() === title;
        })
      : null;
    if (target) {
      window.clearInterval(timer);
      target.click();
      showToast('Yeni eğitim paketi oluşturuldu. Şimdi ders bölümü ve MP4 videolarını ekleyebilirsiniz.');
    } else if (attempts >= 30) {
      window.clearInterval(timer);
      showToast('Yeni eğitim paketi oluşturuldu. “Paketleri yenile” ile listede görebilirsiniz.');
    }
  }, 180);
}

async function sectorOptions() {
  try {
    const meta = await api('/trainings/remote/meta', {_retries: 1});
    const rows = Array.isArray(meta?.sector_catalog) ? meta.sector_catalog : [];
    const supported = rows.filter((row) => SUPPORTED_SECTOR_CODES.has(String(row?.code || '')));
    if (supported.length) return supported;
  } catch (_error) {
    // The modal remains usable with the static labels; the backend still
    // validates the selected sector and fails closed.
  }
  return FALLBACK_SECTORS;
}

async function openDialog() {
  if (!(await resolvePermission())) return;
  ensureStyles();
  closeDialog();

  const overlay = document.createElement('div');
  overlay.className = 'remote-custom-package-overlay';
  overlay.setAttribute(DIALOG_ATTR, 'true');
  overlay.innerHTML = `
    <div class="remote-custom-package-dialog" role="dialog" aria-modal="true" aria-labelledby="remote-custom-package-title">
      <div class="remote-custom-package-head">
        <div>
          <h3 id="remote-custom-package-title">Yeni Eğitim Paketi Oluştur</h3>
          <p>Bu paket yalnız sizin OSGB kapsamınızda oluşturulur. Mevcut ortak eğitim paketleri ve çalışan atamaları değişmez.</p>
        </div>
        <button type="button" class="remote-custom-package-close" aria-label="Kapat">×</button>
      </div>
      <form class="remote-custom-package-body">
        <label class="remote-custom-package-field">
          <span>Eğitim paketi adı *</span>
          <input name="title" maxlength="220" minlength="3" required autocomplete="off" placeholder="Örn. Kapalı Alanda Çalışma Eğitimi" />
        </label>
        <label class="remote-custom-package-field">
          <span>Eğitim / sektör kategorisi *</span>
          <select name="sector_code" required>
            <option value="">Kategori seçin</option>
          </select>
        </label>
        <label class="remote-custom-package-field">
          <span>Kısa açıklama</span>
          <textarea name="description" maxlength="5000" placeholder="Eğitimin kapsamını kısaca açıklayın."></textarea>
        </label>
        <div class="remote-custom-package-rules">
          <strong>Sabit eğitim kuralları:</strong> %100 zorunlu video izleme · ileri sarma kapalı ·
          seçilen sektörün onaylı soru paketinden <strong>tam 10 final sorusu</strong> ·
          geçme puanı <strong>%70</strong>. Rastgele veya uydurma soru üretilmez.
        </div>
        <div class="remote-custom-package-error" role="alert"></div>
        <div class="remote-custom-package-actions">
          <button type="button" class="cancel">Vazgeç</button>
          <button type="submit" class="primary">Kaydet ve Paketi Oluştur</button>
        </div>
      </form>
    </div>
  `;
  document.body.appendChild(overlay);
  document.body.style.overflow = 'hidden';

  const form = overlay.querySelector('form');
  const titleInput = form.querySelector('input[name="title"]');
  const sectorSelect = form.querySelector('select[name="sector_code"]');
  const descriptionInput = form.querySelector('textarea[name="description"]');
  const errorBox = form.querySelector('.remote-custom-package-error');
  const submitButton = form.querySelector('button[type="submit"]');

  const rows = await sectorOptions();
  for (const row of rows) {
    const option = document.createElement('option');
    option.value = row.code;
    option.textContent = row.label || row.code;
    sectorSelect.appendChild(option);
  }

  const displayError = (message) => {
    errorBox.textContent = message || 'Yeni eğitim paketi oluşturulamadı.';
    errorBox.style.display = 'block';
  };

  overlay.querySelector('.remote-custom-package-close')?.addEventListener('click', closeDialog);
  overlay.querySelector('.cancel')?.addEventListener('click', closeDialog);
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) closeDialog();
  });

  const onKeydown = (event) => {
    if (event.key === 'Escape') {
      document.removeEventListener('keydown', onKeydown);
      closeDialog();
    }
  };
  document.addEventListener('keydown', onKeydown, {once: false});

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorBox.style.display = 'none';
    const title = String(titleInput.value || '').trim().replace(/\s+/g, ' ');
    const sectorCode = String(sectorSelect.value || '').trim();
    const description = String(descriptionInput.value || '').trim();

    if (title.length < 3) {
      displayError('Eğitim paketi adını girin.');
      titleInput.focus();
      return;
    }
    if (!SUPPORTED_SECTOR_CODES.has(sectorCode)) {
      displayError('Doğrulanmış soru paketi bulunan bir kategori seçin.');
      sectorSelect.focus();
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = 'Paket oluşturuluyor…';
    try {
      const created = await api('/trainings/remote/catalog/packages', {
        method: 'POST',
        _retries: 0,
        body: JSON.stringify({
          title,
          sector_code: sectorCode,
          description: description || null,
        }),
      });
      document.removeEventListener('keydown', onKeydown);
      closeDialog();

      const section = findCatalogSection();
      const refreshButton = findRefreshButton(section);
      refreshButton?.click();
      focusCreatedPackage(created?.title || title);
    } catch (error) {
      displayError(error?.message || 'Yeni eğitim paketi oluşturulamadı.');
      submitButton.disabled = false;
      submitButton.textContent = 'Kaydet ve Paketi Oluştur';
    }
  });

  window.setTimeout(() => titleInput?.focus(), 0);
}

async function injectTrigger() {
  if (injectionPending) return;
  injectionPending = true;
  try {
    const section = findCatalogSection();
    if (!section || section.querySelector(`[${TRIGGER_ATTR}]`)) return;
    if (!(await resolvePermission())) return;

    const refreshButton = findRefreshButton(section);
    if (!refreshButton?.parentElement) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'remote-custom-package-trigger';
    button.setAttribute(TRIGGER_ATTR, 'true');
    button.textContent = '+ Yeni eğitim paketi';
    button.title = 'Yalnız bu OSGB için sıfırdan yeni eğitim paketi oluştur';
    button.addEventListener('click', () => void openDialog());

    refreshButton.parentElement.insertBefore(button, refreshButton);
  } finally {
    injectionPending = false;
  }
}

const observer = new MutationObserver(() => {
  void injectTrigger();
});
observer.observe(document.documentElement, {subtree: true, childList: true});

window.addEventListener('hashchange', () => {
  window.setTimeout(() => void injectTrigger(), 80);
});
window.addEventListener('isg:auth-lost', () => {
  closeDialog();
  document.querySelector(`[${TRIGGER_ATTR}]`)?.remove();
  permissionPromise = null;
  canCreatePackage = false;
});

void injectTrigger();