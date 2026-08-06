import {api} from './api';
import {
  employmentStatusLabel,
  formatProfileDate,
  normalizeEmployeeRows,
  normalizePersonnelProfileSummary,
  normalizeProfessionalRows,
  shouldRenderPersonnelProfileEntry,
} from './personnel_profile_readonly_logic';
import './personnel_profile_readonly.css';

const ENTRY_CLASS = 'personnel-profile-readonly-entry';
const readinessCache = new Map();
const osgbContextCache = new Map();
let attachTimer = null;
let activeDialog = null;
let returnFocus = null;
let attaching = false;

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function text(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function pageHeading(label) {
  return [...document.querySelectorAll('h1,h2,h3')]
    .find((heading) => text(heading.textContent) === label) || null;
}

function selectedValueByLabel(labelText) {
  const labels = [...document.querySelectorAll('label')];
  const label = labels.find((item) => {
    const caption = item.querySelector('span, strong, b');
    return text(caption?.textContent) === labelText;
  });
  const value = Number(label?.querySelector('select')?.value || 0);
  return value > 0 ? value : null;
}

function removeEntriesExcept(key) {
  document.querySelectorAll(`.${ENTRY_CLASS}`).forEach((entry) => {
    if (String(entry.dataset.contextKey || '') !== String(key || '')) entry.remove();
  });
}

async function readiness(companyId) {
  if (!companyId) return null;
  if (!readinessCache.has(companyId)) {
    readinessCache.set(
      companyId,
      api(`/personnel-profiles/readiness?company_id=${encodeURIComponent(companyId)}`, {_retries: 1})
        .catch(() => null),
    );
  }
  return readinessCache.get(companyId);
}

function entryAnchor(heading) {
  return heading.closest('.page-title') || heading.parentElement || heading;
}

function createEntry({heading, contextKey, title, description, actionLabel, onOpen}) {
  removeEntriesExcept(contextKey);
  let entry = document.querySelector(`.${ENTRY_CLASS}[data-context-key="${contextKey}"]`);
  if (!entry) {
    entry = document.createElement('section');
    entry.className = ENTRY_CLASS;
    entry.dataset.contextKey = contextKey;
    entry.setAttribute('aria-label', title);
    entry.innerHTML = `
      <div class="personnel-profile-readonly-entry__copy">
        <span class="personnel-profile-readonly-entry__eyebrow">Kontrollü pilot · Salt okunur</span>
        <strong>${escapeHtml(title)}</strong>
        <p>${escapeHtml(description)}</p>
      </div>
      <button type="button" class="personnel-profile-readonly-entry__button">
        ${escapeHtml(actionLabel)}
      </button>`;
    entry.querySelector('button')?.addEventListener('click', onOpen);
    entryAnchor(heading).insertAdjacentElement('afterend', entry);
  }
  return entry;
}

function closeDialog() {
  if (!activeDialog) return;
  activeDialog.remove();
  activeDialog = null;
  document.body.style.removeProperty('overflow');
  document.removeEventListener('keydown', onDialogKeydown);
  if (returnFocus?.isConnected) returnFocus.focus();
  returnFocus = null;
}

function onDialogKeydown(event) {
  if (event.key === 'Escape') closeDialog();
}

function openDialog({title, subtitle, rows, loadSummary}) {
  closeDialog();
  returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const overlay = document.createElement('div');
  overlay.className = 'personnel-profile-readonly-dialog';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-labelledby', 'personnelProfileDialogTitle');
  overlay.innerHTML = `
    <div class="personnel-profile-readonly-dialog__card">
      <header class="personnel-profile-readonly-dialog__header">
        <div>
          <span>Kontrollü pilot · Salt okunur</span>
          <h3 id="personnelProfileDialogTitle">${escapeHtml(title)}</h3>
          <p>${escapeHtml(subtitle)}</p>
        </div>
        <button type="button" class="personnel-profile-readonly-dialog__close" data-profile-close aria-label="Personel kartını kapat">×</button>
      </header>
      <div class="personnel-profile-readonly-dialog__safety">
        Bu önizleme mevcut personel kaydını değiştirmez. Sağlık, adli sicil, özel durum ve restricted belgeler gösterilmez.
      </div>
      <div class="personnel-profile-readonly-dialog__layout">
        <nav class="personnel-profile-readonly-dialog__list" aria-label="Personel kartı seçimi">
          ${rows.length ? rows.map((row, index) => `
            <button
              type="button"
              class="personnel-profile-readonly-dialog__person ${index === 0 ? 'is-selected' : ''}"
              data-profile-row="${index}"
            >
              <strong>${escapeHtml(row.fullName)}</strong>
              <span>${escapeHtml(row.jobTitle || row.professionalTypeLabel || row.department || 'Personel')}</span>
              <small>${row.active ? 'Aktif' : 'Pasif / Askıda'}</small>
            </button>`).join('') : '<p class="personnel-profile-readonly-dialog__empty">Görüntülenebilir kayıt bulunamadı.</p>'}
        </nav>
        <section class="personnel-profile-readonly-dialog__detail" aria-live="polite">
          <div class="personnel-profile-readonly-dialog__loading">Profil özeti hazırlanıyor…</div>
        </section>
      </div>
    </div>`;

  overlay.addEventListener('click', (event) => {
    if (event.target === overlay || event.target.closest('[data-profile-close]')) {
      closeDialog();
      return;
    }
    const button = event.target.closest('[data-profile-row]');
    if (!button) return;
    overlay.querySelectorAll('[data-profile-row]').forEach((item) => item.classList.remove('is-selected'));
    button.classList.add('is-selected');
    const row = rows[Number(button.dataset.profileRow || 0)];
    if (row) void renderSummary(overlay, row, loadSummary);
  });

  document.body.appendChild(overlay);
  document.body.style.overflow = 'hidden';
  activeDialog = overlay;
  document.addEventListener('keydown', onDialogKeydown);
  overlay.querySelector('[data-profile-close]')?.focus();
  if (rows[0]) void renderSummary(overlay, rows[0], loadSummary);
}

function detailRow(label, value) {
  if (!value) return '';
  return `<div class="personnel-profile-readonly-dialog__field"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function summaryHtml(summary) {
  if (summary.restrictedDataIncluded) {
    return `
      <div class="personnel-profile-readonly-dialog__error" role="alert">
        Güvenlik kontrolü bu yanıtı engelledi. Restricted veri işareti bulunan profil ekranda gösterilmedi.
      </div>`;
  }

  const isProfessional = summary.subjectType === 'professional';
  const subtitle = isProfessional
    ? summary.professionalTypeLabel
    : [summary.jobTitle, summary.department].filter(Boolean).join(' · ') || 'İşyeri personeli';
  return `
    <div class="personnel-profile-readonly-dialog__summary">
      <div class="personnel-profile-readonly-dialog__identity">
        <div class="personnel-profile-readonly-dialog__avatar" aria-hidden="true">
          ${escapeHtml(summary.fullName.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || 'P')}
        </div>
        <div>
          <span>${escapeHtml(isProfessional ? 'Profesyonel Personel Profili' : 'Dijital Personel Kartı')}</span>
          <h4>${escapeHtml(summary.fullName || 'Personel')}</h4>
          <p>${escapeHtml(subtitle)}</p>
        </div>
        <span class="personnel-profile-readonly-dialog__status">${escapeHtml(employmentStatusLabel(summary.employmentStatus))}</span>
      </div>
      <div class="personnel-profile-readonly-dialog__grid">
        ${detailRow('İşyeri', summary.companyName)}
        ${detailRow('Şube', summary.branchName)}
        ${detailRow('Maskeli kimlik', summary.nationalIdentityMasked)}
        ${detailRow('Görev', summary.jobTitle)}
        ${detailRow('Departman', summary.department)}
        ${detailRow('İşe giriş', formatProfileDate(summary.employmentStartDate))}
        ${detailRow('Mesleki rol', isProfessional ? summary.professionalTypeLabel : '')}
        ${detailRow('E-posta', summary.email)}
        ${detailRow('Telefon', summary.phone)}
        ${detailRow('Belge sınıfı', summary.certificateClass)}
        ${detailRow('Belge numarası', summary.certificateNumber)}
        ${detailRow('Belge tarihi', formatProfileDate(summary.certificateDate))}
        ${detailRow('Aktif görevlendirme', isProfessional ? String(summary.activeAssignmentCount) : '')}
      </div>
      <footer>
        <strong>Veri minimizasyonu etkin</strong>
        <span>Bu ekran yalnız onaylı minimum alanları gösterir; kayıt düzenleme ve belge işlemi içermez.</span>
      </footer>
    </div>`;
}

async function renderSummary(overlay, row, loadSummary) {
  const detail = overlay.querySelector('.personnel-profile-readonly-dialog__detail');
  if (!detail) return;
  detail.innerHTML = '<div class="personnel-profile-readonly-dialog__loading">Profil özeti hazırlanıyor…</div>';
  try {
    const payload = await loadSummary(row);
    if (!overlay.isConnected) return;
    detail.innerHTML = summaryHtml(normalizePersonnelProfileSummary(payload));
  } catch (error) {
    if (!overlay.isConnected) return;
    detail.innerHTML = `
      <div class="personnel-profile-readonly-dialog__error" role="alert">
        ${escapeHtml(error?.message || 'Profil özeti yüklenemedi.')}
      </div>`;
  }
}

async function attachEmployeeEntry(heading) {
  const companyId = selectedValueByLabel('İşyeri');
  if (!companyId) {
    removeEntriesExcept('');
    return;
  }
  const payload = await readiness(companyId);
  if (!shouldRenderPersonnelProfileEntry(payload)) {
    removeEntriesExcept('');
    return;
  }
  createEntry({
    heading,
    contextKey: `employee:${companyId}`,
    title: 'Dijital Personel Kartları',
    description: 'Seçili işyerindeki personelin veri-minimum, salt okunur profil özetlerini görüntüler.',
    actionLabel: 'Personel Kartlarını Görüntüle',
    onOpen: async () => {
      const employees = normalizeEmployeeRows(
        await api(`/employees?company_id=${encodeURIComponent(companyId)}&include_inactive=true`),
      );
      openDialog({
        title: 'Dijital Personel Kartları',
        subtitle: `${employees.length} personel · düzenleme yapılmaz`,
        rows: employees,
        loadSummary: (row) => api(`/personnel-profiles/employee/${row.id}/summary`),
      });
    },
  });
}

async function activeProfessionalContext(osgbId) {
  if (!osgbId) return null;
  if (!osgbContextCache.has(osgbId)) {
    osgbContextCache.set(osgbId, (async () => {
      const [professionals, assignments] = await Promise.all([
        api(`/osgb/professionals?osgb_id=${encodeURIComponent(osgbId)}`),
        api(`/osgb/assignments?osgb_id=${encodeURIComponent(osgbId)}`),
      ]);
      const assignmentRows = Array.isArray(assignments) ? assignments : assignments?.rows || [];
      const candidateCompanyIds = [...new Set(assignmentRows
        .filter((row) => !row?.status || String(row.status).toLowerCase() === 'active')
        .map((row) => Number(row?.company_id || 0))
        .filter((value) => value > 0))].slice(0, 50);
      const readinessRows = await Promise.all(candidateCompanyIds.map(async (companyId) => ({
        companyId,
        payload: await readiness(companyId),
      })));
      const pilotCompanyIds = new Set(
        readinessRows
          .filter((row) => shouldRenderPersonnelProfileEntry(row.payload))
          .map((row) => row.companyId),
      );
      return {
        pilotCompanyIds,
        rows: normalizeProfessionalRows(professionals, assignments, pilotCompanyIds),
      };
    })().catch(() => null));
  }
  return osgbContextCache.get(osgbId);
}

async function resolveOsgbId() {
  const selected = selectedValueByLabel('OSGB');
  if (selected) return selected;
  try {
    const rows = await api('/osgb', {_retries: 1});
    const list = Array.isArray(rows) ? rows : rows?.rows || [];
    const id = Number(list[0]?.id || 0);
    return id > 0 ? id : null;
  } catch {
    return null;
  }
}

async function attachProfessionalEntry(heading) {
  const osgbId = await resolveOsgbId();
  if (!osgbId) {
    removeEntriesExcept('');
    return;
  }
  const context = await activeProfessionalContext(osgbId);
  if (!context?.rows?.length) {
    removeEntriesExcept('');
    return;
  }
  createEntry({
    heading,
    contextKey: `professional:${osgbId}`,
    title: 'Profesyonel Personel Profilleri',
    description: 'Pilot işyerlerine aktif atanmış uzman, hekim ve diğer sağlık personelinin minimum özetlerini görüntüler.',
    actionLabel: 'Profesyonel Profilleri Görüntüle',
    onOpen: () => {
      openDialog({
        title: 'Profesyonel Personel Profilleri',
        subtitle: `${context.rows.length} profesyonel · aktif görevlendirme kontrolü`,
        rows: context.rows,
        loadSummary: (row) => api(
          `/personnel-profiles/professional/${row.id}/summary?company_id=${encodeURIComponent(row.companyId)}`,
        ),
      });
    },
  });
}

async function attach() {
  if (attaching) return;
  attaching = true;
  try {
    const employeeHeading = pageHeading('Personel Yönetimi');
    if (employeeHeading) {
      await attachEmployeeEntry(employeeHeading);
      return;
    }
    const professionalHeading = pageHeading('İSG Profesyonelleri');
    if (professionalHeading) {
      await attachProfessionalEntry(professionalHeading);
      return;
    }
    removeEntriesExcept('');
  } finally {
    attaching = false;
  }
}

function scheduleAttach() {
  clearTimeout(attachTimer);
  attachTimer = setTimeout(() => void attach(), 120);
}

new MutationObserver(scheduleAttach).observe(document.documentElement, {
  childList: true,
  subtree: true,
});
window.addEventListener('popstate', scheduleAttach);
window.addEventListener('hashchange', scheduleAttach);
scheduleAttach();
