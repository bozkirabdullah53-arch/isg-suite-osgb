import {api} from './api';

const CATALOG_API = '/trainings/remote/catalog/packages';
const STYLE_ID = 'remote-training-package-management-style';
const TOOLBAR_ATTR = 'data-remote-package-management-toolbar';
const SECTION_ACTION_ATTR = 'data-remote-section-management-actions';
const SECTION_ROOT_ATTR = 'data-remote-catalog-section-root';
const SECTION_HANDLE_ATTR = 'data-remote-section-drag-handle';
const DIALOG_ATTR = 'data-remote-package-management-dialog';

let allowed = null;
let packageRows = [];
let selectedPackageId = null;
let selectedDetail = null;
let packageLoadPromise = null;
let renderPending = false;
let forceRequested = false;
let sectionReorderEnabled = false;
let sectionReorderSaving = false;
let draggingSectionRoot = null;
let dragStartSectionOrder = null;
let dragStartSectionContainer = null;
let dragDropCommitted = false;
const boundSectionRoots = new WeakSet();

function ensureStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    .rt-package-manage-toolbar{margin-top:12px;padding:12px;border:1px solid #b8d8d5;border-radius:10px;background:#f4fbfa;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
    .rt-package-manage-toolbar__text{color:#31566b;font-size:12px;line-height:1.45}.rt-package-manage-toolbar__text strong{color:#0f766e}
    .rt-package-manage-toolbar__actions,.rt-section-manage-actions{display:flex;gap:7px;flex-wrap:wrap}
    .rt-package-manage-btn,.rt-section-manage-actions button{min-height:34px;padding:7px 10px;border:1px solid #a9c9c6;border-radius:8px;background:#fff;color:#174b57;font-weight:750;cursor:pointer}
    .rt-section-manage-actions{display:inline-flex;margin-left:10px;vertical-align:middle}.rt-section-manage-actions button{min-height:29px;padding:4px 8px;font-size:12px}
    .rt-package-manage-btn--danger,.rt-section-manage-actions button:last-child{border-color:#e6a19a;color:#a5271f;background:#fff8f7}
    .rt-section-reorder-hint{margin-top:8px;color:#31566b;font-size:12px;line-height:1.45}
    .rt-section-sort-root{transition:opacity .15s ease,outline-color .15s ease,background-color .15s ease}
    .rt-section-sort-root.is-dragging{opacity:.48}
    .rt-section-sort-root.is-drop-target{outline:2px solid #159f9a;outline-offset:3px;background:#f2fffd}
    .rt-section-drag-handle{display:inline-flex;align-items:center;gap:5px;min-height:28px;margin:0 7px 5px 0;padding:4px 8px;border:1px dashed #56a7a5;border-radius:7px;background:#f2fbfa;color:#0f766e;font:inherit;font-size:12px;font-weight:800;cursor:grab;user-select:none}
    .rt-section-drag-handle:active{cursor:grabbing}
    .rt-section-drag-handle[aria-disabled="true"]{opacity:.6;cursor:not-allowed}
    .rt-pm-overlay{position:fixed;inset:0;z-index:10120;display:grid;place-items:center;padding:22px;background:rgba(8,25,39,.58);backdrop-filter:blur(2px)}
    .rt-pm-dialog{width:min(620px,96vw);max-height:92vh;overflow:auto;border-radius:16px;background:#fff;border:1px solid #dbe5ef;box-shadow:0 24px 70px rgba(7,30,48,.28)}
    .rt-pm-head{display:flex;justify-content:space-between;gap:14px;padding:19px 21px 13px;border-bottom:1px solid #e6edf3}.rt-pm-head h3{margin:0;color:#173b57;font-size:20px}.rt-pm-head p{margin:6px 0 0;color:#5e7485;font-size:12px;line-height:1.45}
    .rt-pm-close{border:0;background:transparent;font-size:26px;cursor:pointer;color:#496174}.rt-pm-form{padding:18px 21px 21px}.rt-pm-field{display:block;margin-bottom:14px}.rt-pm-field>span{display:block;margin-bottom:6px;color:#24465f;font-size:13px;font-weight:750}
    .rt-pm-field input[type=text],.rt-pm-field textarea{width:100%;box-sizing:border-box;border:1px solid #bfd0dc;border-radius:9px;padding:10px 11px;font:inherit;color:#173b57}.rt-pm-field textarea{min-height:95px;resize:vertical}
    .rt-pm-check{display:flex;align-items:center;gap:8px;color:#36556d;font-size:13px;margin:4px 0 14px}.rt-pm-error{display:none;margin-bottom:12px;padding:9px 11px;border-radius:8px;background:#fff2f0;color:#b42318;font-size:12px;font-weight:700}
    .rt-pm-actions{display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap}.rt-pm-actions button{min-height:38px;padding:8px 12px;border:1px solid #bfd0dc;border-radius:8px;background:#fff;color:#24465f;font-weight:750;cursor:pointer}.rt-pm-actions .primary{background:#0f766e;border-color:#0f766e;color:#fff}
    .rt-pm-toast{position:fixed;z-index:10150;right:22px;bottom:22px;max-width:min(480px,90vw);padding:12px 14px;border-radius:10px;background:#0f766e;color:#fff;box-shadow:0 12px 34px rgba(8,40,55,.24);font-size:13px;font-weight:700}.rt-pm-toast--error{background:#b42318}
  `;
  document.head.appendChild(style);
}

function catalogSection() {
  return [...document.querySelectorAll('section')].find((section) => {
    const text = section.textContent || '';
    return text.includes('Uzaktan Eğitim Paket Kataloğu') && text.includes('Sektör eğitim paketleri');
  }) || null;
}

function packageListPanel(section = catalogSection()) {
  const heading = section ? [...section.querySelectorAll('h4')].find((node) => node.textContent?.trim() === 'Sektör eğitim paketleri') : null;
  return heading?.parentElement || null;
}

function packageCardButtons(section = catalogSection()) {
  const panel = packageListPanel(section);
  return panel ? [...panel.querySelectorAll('button')].filter((button) => button.querySelector('strong')) : [];
}

function refreshButton(section = catalogSection()) {
  return section ? [...section.querySelectorAll('button')].find((button) => button.textContent?.trim() === 'Paketleri yenile') || null : null;
}

function showToast(message, error = false) {
  document.querySelector('.rt-pm-toast')?.remove();
  const node = document.createElement('div');
  node.className = `rt-pm-toast${error ? ' rt-pm-toast--error' : ''}`;
  node.setAttribute('role', error ? 'alert' : 'status');
  node.textContent = message;
  document.body.appendChild(node);
  window.setTimeout(() => node.remove(), error ? 6500 : 4500);
}

async function canManage() {
  if (allowed !== null) return allowed;
  try {
    const user = await api('/auth/me', {_retries: 1});
    allowed = Boolean(user?.role === 'company_admin' && Number(user?.osgb_id || 0) > 0 && !user?.company_id);
  } catch (_error) {
    allowed = false;
  }
  return allowed;
}

async function loadPackageRows(force = false) {
  if (!force && packageRows.length) return packageRows;
  if (!packageLoadPromise) {
    packageLoadPromise = api(CATALOG_API, {_retries: 1})
      .then((rows) => {
        packageRows = Array.isArray(rows) ? rows : [];
        return packageRows;
      })
      .finally(() => { packageLoadPromise = null; });
  }
  return packageLoadPromise;
}

function selectedCardIndex() {
  const buttons = packageCardButtons();
  for (let index = 0; index < buttons.length; index += 1) {
    const row = buttons[index].parentElement;
    if (row && window.getComputedStyle(row).borderTopColor === 'rgb(11, 156, 168)') return index;
  }
  return -1;
}

function detailHeadingTitle(section = catalogSection()) {
  if (!section) return '';
  return [...section.querySelectorAll('h4')]
    .map((node) => node.textContent?.trim() || '')
    .find((text) => text && text !== 'Sektör eğitim paketleri') || '';
}

async function resolveSelectedPackageId() {
  const rows = await loadPackageRows();
  if (selectedPackageId && rows.some((row) => Number(row.id) === Number(selectedPackageId))) return selectedPackageId;
  const index = selectedCardIndex();
  if (index >= 0 && rows[index]?.id) return (selectedPackageId = Number(rows[index].id));
  const title = detailHeadingTitle();
  const matches = title ? rows.filter((row) => String(row.title || '').trim() === title) : [];
  if (matches.length === 1) return (selectedPackageId = Number(matches[0].id));
  return null;
}

async function resolveSelectedDetail(force = false) {
  const id = await resolveSelectedPackageId();
  if (!id) return null;
  if (!force && selectedDetail && Number(selectedDetail.id) === Number(id)) return selectedDetail;
  try {
    selectedDetail = await api(`${CATALOG_API}/${id}`, {_retries: 1});
    return selectedDetail;
  } catch (_error) {
    selectedDetail = null;
    return null;
  }
}

function closeDialog() {
  document.querySelector(`[${DIALOG_ATTR}]`)?.remove();
  document.body.style.removeProperty('overflow');
}

function dialogShell(title, note) {
  ensureStyles();
  closeDialog();
  const overlay = document.createElement('div');
  overlay.className = 'rt-pm-overlay';
  overlay.setAttribute(DIALOG_ATTR, 'true');
  overlay.innerHTML = `<div class="rt-pm-dialog" role="dialog" aria-modal="true"><div class="rt-pm-head"><div><h3></h3><p></p></div><button type="button" class="rt-pm-close" aria-label="Kapat">×</button></div><form class="rt-pm-form"></form></div>`;
  overlay.querySelector('h3').textContent = title;
  overlay.querySelector('p').textContent = note;
  document.body.appendChild(overlay);
  document.body.style.overflow = 'hidden';
  overlay.querySelector('.rt-pm-close')?.addEventListener('click', closeDialog);
  overlay.addEventListener('click', (event) => { if (event.target === overlay) closeDialog(); });
  return {form: overlay.querySelector('form')};
}

async function refreshCurrentPackage() {
  sectionReorderEnabled = false;
  selectedDetail = null;
  await loadPackageRows(true);
  refreshButton()?.click();
  window.setTimeout(() => {
    selectedDetail = null;
    scheduleRender(true);
  }, 450);
}


function sectionRootForItem(sectionRoot, item) {
  const wanted = String(item.code || '') + ' · ' + String(item.title || '');
  const label = [...sectionRoot.querySelectorAll('strong')]
    .find((node) => node.textContent?.trim() === wanted);
  // strong -> heading group -> header row -> complete section card
  return label?.parentElement?.parentElement?.parentElement || null;
}

function sectionRootsInOrder(sectionContainer) {
  if (!sectionContainer) return [];
  return [...sectionContainer.children]
    .filter((node) => node.matches?.('[' + SECTION_ROOT_ATTR + ']'))
    .filter((node) => node.dataset.remoteCatalogSectionId);
}

function sectionOrderFromDom(sectionContainer) {
  return sectionRootsInOrder(sectionContainer)
    .map((node) => Number(node.dataset.remoteCatalogSectionId))
    .filter((id) => Number.isInteger(id) && id > 0);
}

function applySectionOrder(sectionContainer, orderedIds) {
  const roots = sectionRootsInOrder(sectionContainer);
  const byId = new Map(roots.map((root) => [Number(root.dataset.remoteCatalogSectionId), root]));
  let cursor = roots[0] || null;
  for (const id of orderedIds) {
    const root = byId.get(Number(id));
    if (!root) continue;
    if (root !== cursor) {
      if (cursor) sectionContainer.insertBefore(root, cursor);
      else sectionContainer.appendChild(root);
    }
    cursor = root.nextElementSibling;
  }
}

function clearDragState() {
  document.querySelectorAll('[' + SECTION_ROOT_ATTR + ']').forEach((node) => {
    node.classList.remove('is-dragging', 'is-drop-target');
  });
  draggingSectionRoot = null;
  dragStartSectionOrder = null;
  dragStartSectionContainer = null;
  dragDropCommitted = false;
}

async function persistSectionOrder(detail, sectionContainer, previousOrder, nextOrder) {
  if (!detail?.id) {
    applySectionOrder(sectionContainer, previousOrder);
    showToast('Bölüm sırası kaydedilemedi; paket bilgisi yenileniyor.', true);
    return;
  }
  if (sectionReorderSaving || !nextOrder.length || previousOrder.join(',') === nextOrder.join(',')) return;
  sectionReorderSaving = true;
  try {
    await api(CATALOG_API + '/' + detail.id + '/sections/order', {
      method: 'PATCH',
      _retries: 0,
      body: JSON.stringify({section_ids: nextOrder}),
    });
    showToast('Bölüm sırası kaydedildi. Yeni firma/çalışan eğitim kopyaları bu sırayı kullanacak.');
    await refreshCurrentPackage();
  } catch (error) {
    applySectionOrder(sectionContainer, previousOrder);
    showToast(error?.message || 'Bölüm sırası kaydedilemedi; eski sıra geri yüklendi.', true);
  } finally {
    sectionReorderSaving = false;
    scheduleRender(true);
  }
}

function bindSectionReorder(sectionRoot, item, label, detail) {
  const root = sectionRootForItem(sectionRoot, item);
  if (!root || !label) return null;
  root.setAttribute(SECTION_ROOT_ATTR, 'true');
  root.dataset.remoteCatalogSectionId = String(item.id);
  root.classList.add('rt-section-sort-root');

  const headingGroup = label.parentElement;
  let handle = headingGroup?.querySelector('[' + SECTION_HANDLE_ATTR + ']');
  if (!handle && headingGroup) {
    handle = document.createElement('button');
    handle.type = 'button';
    handle.setAttribute(SECTION_HANDLE_ATTR, 'true');
    handle.className = 'rt-section-drag-handle';
    handle.textContent = '☷ Tut ve taşı';
    handle.title = 'Bölümü fareyle tutup istediğiniz sıraya taşıyın';
    handle.setAttribute('aria-label', String(item.title || 'Bölüm') + ' bölümünü sırada taşımak için tutun');
    headingGroup.insertBefore(handle, headingGroup.firstChild);
  }
  if (!handle) return root;

  handle.draggable = !sectionReorderSaving;
  handle.setAttribute('aria-disabled', sectionReorderSaving ? 'true' : 'false');
  if (!handle.dataset.reorderBound) {
    handle.dataset.reorderBound = 'true';
    handle.addEventListener('dragstart', (event) => {
      if (!sectionReorderEnabled || sectionReorderSaving) {
        event.preventDefault();
        return;
      }
      dragDropCommitted = false;
      draggingSectionRoot = root;
      dragStartSectionContainer = root.parentElement;
      dragStartSectionOrder = sectionOrderFromDom(dragStartSectionContainer);
      root.classList.add('is-dragging');
      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', String(item.id));
      }
    });
    handle.addEventListener('dragend', () => {
      if (draggingSectionRoot && !dragDropCommitted && dragStartSectionContainer && dragStartSectionOrder) {
        applySectionOrder(dragStartSectionContainer, dragStartSectionOrder);
      }
      clearDragState();
    });
  }

  if (!boundSectionRoots.has(root)) {
    boundSectionRoots.add(root);
    root.addEventListener('dragover', (event) => {
      if (!sectionReorderEnabled || !draggingSectionRoot || draggingSectionRoot === root) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
      document.querySelectorAll('[' + SECTION_ROOT_ATTR + ']').forEach((node) => node.classList.remove('is-drop-target'));
      root.classList.add('is-drop-target');
      const rect = root.getBoundingClientRect();
      const before = event.clientY < rect.top + (rect.height / 2);
      const reference = before ? root : root.nextElementSibling;
      if (reference && reference !== draggingSectionRoot) root.parentElement?.insertBefore(draggingSectionRoot, reference);
      else if (!reference && draggingSectionRoot.parentElement === root.parentElement) root.parentElement.appendChild(draggingSectionRoot);
    });
    root.addEventListener('drop', (event) => {
      if (!sectionReorderEnabled || !draggingSectionRoot || draggingSectionRoot === root) return;
      event.preventDefault();
      const container = dragStartSectionContainer || draggingSectionRoot.parentElement;
      const previousOrder = dragStartSectionOrder ? [...dragStartSectionOrder] : [];
      const nextOrder = sectionOrderFromDom(container);
      dragDropCommitted = true;
      clearDragState();
      void persistSectionOrder(detail, container, previousOrder, nextOrder);
    });
  }
  return root;
}

function removeSectionReorderControls() {
  sectionReorderEnabled = false;
  document.querySelectorAll('[' + SECTION_HANDLE_ATTR + ']').forEach((node) => node.remove());
  document.querySelectorAll('[' + SECTION_ROOT_ATTR + ']').forEach((node) => {
    node.classList.remove('rt-section-sort-root', 'is-dragging', 'is-drop-target');
    node.removeAttribute(SECTION_ROOT_ATTR);
    delete node.dataset.remoteCatalogSectionId;
  });
  clearDragState();
}

function openPackageEdit(detail) {
  const {form} = dialogShell('Eğitim Paketini Düzenle', 'Paket adı ve açıklaması değiştirilebilir. Daha önce firmaya hazırlanmış çalışan kopyaları geriye dönük değişmez.');
  form.innerHTML = `<label class="rt-pm-field"><span>Paket adı *</span><input type="text" name="title" maxlength="220" required /></label><label class="rt-pm-field"><span>Açıklama</span><textarea name="description" maxlength="5000"></textarea></label><div class="rt-pm-error" role="alert"></div><div class="rt-pm-actions"><button type="button" class="cancel">Vazgeç</button><button type="submit" class="primary">Değişiklikleri Kaydet</button></div>`;
  const title = form.querySelector('[name=title]');
  const description = form.querySelector('[name=description]');
  const errorBox = form.querySelector('.rt-pm-error');
  title.value = detail.title || '';
  description.value = detail.description || '';
  form.querySelector('.cancel')?.addEventListener('click', closeDialog);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const cleanTitle = String(title.value || '').trim().replace(/\s+/g, ' ');
    if (cleanTitle.length < 3) {
      errorBox.textContent = 'Paket adı en az 3 karakter olmalıdır.';
      errorBox.style.display = 'block';
      return;
    }
    const submit = form.querySelector('[type=submit]');
    submit.disabled = true;
    try {
      await api(`${CATALOG_API}/${detail.id}`, {method: 'PATCH', _retries: 0, body: JSON.stringify({title: cleanTitle, description: String(description.value || '').trim() || null})});
      closeDialog();
      showToast('Paket bilgileri güncellendi.');
      await refreshCurrentPackage();
    } catch (error) {
      errorBox.textContent = error?.message || 'Paket bilgileri güncellenemedi.';
      errorBox.style.display = 'block';
      submit.disabled = false;
    }
  });
  window.setTimeout(() => title.focus(), 0);
}

async function deletePackage(detail) {
  if (!window.confirm(`“${detail.title}” paketi katalogdan kalıcı olarak silinsin mi?\n\nDaha önce firmaya hazırlanmış çalışan eğitimleri, izleme/sınav kayıtları ve belgeler korunur; yalnızca bu katalog paketi ve kaynak videoları kaldırılır.`)) return;
  try {
    const out = await api(`${CATALOG_API}/${detail.id}`, {method: 'DELETE', _retries: 0});
    const preserved = Number(out?.materialized_program_count || 0);
    const message = preserved
      ? `Paket silindi; ${preserved} firma eğitim kopyasının çalışan ve belge geçmişi korundu.`
      : 'Paket silindi.';
    showToast(out?.storage_cleanup_pending ? `${message} Depolama temizliği arka planda tamamlanacak.` : message);
    window.setTimeout(() => window.location.reload(), 300);
  } catch (error) {
    showToast(error?.message || 'Paket silinemedi.', true);
  }
}

function openSectionEdit(detail, item) {
  const {form} = dialogShell('Ders Bölümünü Düzenle', `${detail.title} içindeki bölüm bilgileri değiştirilebilir. Önceki firma/çalışan kopyaları değişmez.`);
  form.innerHTML = `<label class="rt-pm-field"><span>Bölüm kodu *</span><input type="text" name="code" maxlength="64" required /></label><label class="rt-pm-field"><span>Bölüm adı *</span><input type="text" name="title" maxlength="220" required /></label><label class="rt-pm-field"><span>Açıklama</span><textarea name="description" maxlength="5000"></textarea></label><label class="rt-pm-check"><input type="checkbox" name="required" /> Zorunlu bölüm</label><div class="rt-pm-error" role="alert"></div><div class="rt-pm-actions"><button type="button" class="cancel">Vazgeç</button><button type="submit" class="primary">Bölümü Güncelle</button></div>`;
  const code = form.querySelector('[name=code]');
  const title = form.querySelector('[name=title]');
  const description = form.querySelector('[name=description]');
  const required = form.querySelector('[name=required]');
  const errorBox = form.querySelector('.rt-pm-error');
  code.value = item.code || '';
  title.value = item.title || '';
  description.value = item.description || '';
  required.checked = item.is_required !== false;
  form.querySelector('.cancel')?.addEventListener('click', closeDialog);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const cleanCode = String(code.value || '').trim().replace(/\s+/g, ' ');
    const cleanTitle = String(title.value || '').trim().replace(/\s+/g, ' ');
    if (cleanCode.length < 2 || cleanTitle.length < 2) {
      errorBox.textContent = 'Bölüm kodu ve bölüm adı birlikte girilmelidir.';
      errorBox.style.display = 'block';
      return;
    }
    const submit = form.querySelector('[type=submit]');
    submit.disabled = true;
    try {
      await api(`/trainings/remote/catalog/sections/${item.id}`, {method: 'PATCH', _retries: 0, body: JSON.stringify({code: cleanCode, title: cleanTitle, description: String(description.value || '').trim() || null, is_required: Boolean(required.checked)})});
      closeDialog();
      showToast('Ders bölümü güncellendi.');
      await refreshCurrentPackage();
    } catch (error) {
      errorBox.textContent = error?.message || 'Ders bölümü güncellenemedi.';
      errorBox.style.display = 'block';
      submit.disabled = false;
    }
  });
  window.setTimeout(() => code.focus(), 0);
}

async function deleteSection(detail, item) {
  const videoCount = Array.isArray(item.videos) ? item.videos.length : 0;
  const warning = `“${item.code} · ${item.title}” bölümü silinsin mi?${videoCount ? `\n\nBu bölümde ${videoCount} video bulunuyor; paket kataloğundaki bu videolar da silinecek.` : ''}\n\nDaha önce firmaya hazırlanmış çalışan eğitim kopyaları değişmez.`;
  if (!window.confirm(warning)) return;
  try {
    const out = await api(`/trainings/remote/catalog/sections/${item.id}`, {method: 'DELETE', _retries: 0});
    showToast(out?.storage_cleanup_pending ? 'Bölüm silindi; depolama temizliğinin bir kısmı arka planda tamamlanacak.' : 'Bölüm silindi.');
    await refreshCurrentPackage();
  } catch (error) {
    showToast(error?.message || 'Bölüm silinemedi.', true);
  }
}

function removeInjectedControls() {
  document.querySelector(`[${TOOLBAR_ATTR}]`)?.remove();
  document.querySelectorAll(`[${SECTION_ACTION_ATTR}]`).forEach((node) => node.remove());
  removeSectionReorderControls();
}

function addToolbar(sectionRoot, detail, heading) {
  const topRow = heading.parentElement?.parentElement;
  if (!topRow?.parentElement) return null;
  const toolbar = document.createElement('div');
  toolbar.className = 'rt-package-manage-toolbar';
  toolbar.setAttribute(TOOLBAR_ATTR, 'true');
  toolbar.dataset.packageId = String(detail.id);
  toolbar.innerHTML = '<div class="rt-package-manage-toolbar__text"><strong>Paket yönetimi:</strong> Paket adını/açıklamasını değiştirebilir ve OSGB özel paketini silebilirsiniz. Daha önce hazırlanmış firma/çalışan kopyaları korunur.' + (detail.status === 'archived' ? ' İçeriği değiştirmek için önce paketi düzenlemeye açın.' : '') + '<div class="rt-section-reorder-hint">Bölüm sırası: <strong>☷ Tut ve taşı</strong> düğmesine basılı tutup bölümü istediğiniz yere bırakın. Sıra otomatik kaydedilir; daha önce firmaya hazırlanmış çalışan kopyaları geriye dönük değişmez.</div></div><div class="rt-package-manage-toolbar__actions"><button type="button" class="rt-package-manage-btn edit">Paket Bilgilerini Düzenle</button><button type="button" class="rt-package-manage-btn rt-package-manage-btn--danger delete">Paketi Sil</button></div>';
  toolbar.querySelector('.edit')?.addEventListener('click', () => openPackageEdit(detail));
  toolbar.querySelector('.delete')?.addEventListener('click', () => void deletePackage(detail));
  topRow.insertAdjacentElement('afterend', toolbar);
  return toolbar;
}

async function renderControls(forceDetail = false) {
  renderPending = false;
  if (!(await canManage())) return;
  const sectionRoot = catalogSection();
  if (!sectionRoot) return;
  const detail = await resolveSelectedDetail(forceDetail);
  if (!detail) return;

  const existingToolbar = sectionRoot.querySelector(`[${TOOLBAR_ATTR}]`);
  if (detail.is_shared) {
    if (existingToolbar || sectionRoot.querySelector(`[${SECTION_ACTION_ATTR}]`)) removeInjectedControls();
    return;
  }

  const heading = [...sectionRoot.querySelectorAll('h4')].find((node) => node.textContent?.trim() === String(detail.title || '').trim());
  if (!heading) return;

  let toolbar = existingToolbar;
  if (forceDetail || !toolbar || toolbar.dataset.packageId !== String(detail.id)) {
    removeInjectedControls();
    toolbar = addToolbar(sectionRoot, detail, heading);
  }
  if (!toolbar) return;

  if (detail.status === 'archived') {
    sectionRoot.querySelectorAll(`[${SECTION_ACTION_ATTR}]`).forEach((node) => node.remove());
    removeSectionReorderControls();
    return;
  }

  sectionReorderEnabled = true;
  for (const item of detail.sections || []) {
    const wanted = `${item.code} · ${item.title}`;
    const label = [...sectionRoot.querySelectorAll('strong')].find((node) => node.textContent?.trim() === wanted);
    if (!label) continue;
    bindSectionReorder(sectionRoot, item, label, detail);
    if (label.parentElement?.querySelector(`[${SECTION_ACTION_ATTR}]`)) continue;
    const actions = document.createElement('span');
    actions.className = 'rt-section-manage-actions';
    actions.setAttribute(SECTION_ACTION_ATTR, 'true');
    actions.dataset.sectionId = String(item.id);
    actions.innerHTML = '<button type="button">Düzenle</button><button type="button">Bölümü Sil</button>';
    const [editButton, deleteButton] = actions.querySelectorAll('button');
    editButton.addEventListener('click', () => openSectionEdit(detail, item));
    deleteButton.addEventListener('click', () => void deleteSection(detail, item));
    label.insertAdjacentElement('afterend', actions);
  }
}

function scheduleRender(forceDetail = false) {
  forceRequested = forceRequested || forceDetail;
  if (renderPending) return;
  renderPending = true;
  window.setTimeout(() => {
    const force = forceRequested;
    forceRequested = false;
    void renderControls(force);
  }, 120);
}

document.addEventListener('click', (event) => {
  const clickedButton = event.target.closest?.('button');
  const cards = packageCardButtons();
  const index = clickedButton ? cards.indexOf(clickedButton) : -1;
  if (index >= 0) {
    void loadPackageRows().then((rows) => {
      if (rows[index]?.id) {
        selectedPackageId = Number(rows[index].id);
        selectedDetail = null;
        scheduleRender(true);
      }
    });
    return;
  }

  const text = clickedButton?.textContent?.trim() || '';
  if (['Paketi düzenlemeye aç', 'Paketi yayımla', 'Yayından kaldır', 'Arşivle', 'İncelemeye hazır'].includes(text)) {
    window.setTimeout(() => {
      selectedDetail = null;
      scheduleRender(true);
    }, 450);
  }
}, true);

const observer = new MutationObserver(() => scheduleRender(false));
observer.observe(document.documentElement, {childList: true, subtree: true});

window.addEventListener('hashchange', () => {
  selectedPackageId = null;
  selectedDetail = null;
  packageRows = [];
  removeInjectedControls();
  scheduleRender(true);
});

window.addEventListener('isg:auth-lost', () => {
  allowed = null;
  selectedPackageId = null;
  selectedDetail = null;
  packageRows = [];
  closeDialog();
  removeInjectedControls();
});

scheduleRender(true);
