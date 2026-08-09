import {api, authBlobUrl} from './api';
import {
  approvalMethodLabel,
  formatFileSize,
  normalizePresentationReadiness,
  normalizePresentationVersions,
  parseSavedTrainingId,
  presentationActionState,
  presentationStatusLabel,
  shouldRenderPresentationPanel,
} from './training_presentation_readiness_logic';
import './training_presentation_readiness.css';

const PANEL_CLASS = 'training-presentation-panel';
const readinessCache = new Map();
const versionsCache = new Map();
const panelState = new Map();
const inFlight = new Set();
let timer = null;
let activeDialog = null;
let dialogReturnFocus = null;

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function outputPanel() {
  return document.querySelector('section.education-output-panel');
}

function getState(trainingId) {
  if (!panelState.has(trainingId)) {
    panelState.set(trainingId, {busy: '', message: '', error: ''});
  }
  return panelState.get(trainingId);
}

function setState(trainingId, patch) {
  panelState.set(trainingId, {...getState(trainingId), ...patch});
}

function removePanelsExcept(trainingId) {
  document.querySelectorAll(`.${PANEL_CLASS}`).forEach((panel) => {
    if (String(panel.dataset.trainingId || '') !== String(trainingId || '')) panel.remove();
  });
}

function statusBadgeClass(status) {
  return {
    generated: 'badge-ok',
    approved: 'badge-ok',
    archived: 'badge-neutral',
    failed: 'badge-danger',
    draft: 'badge-warn',
  }[String(status || '').toLowerCase()] || 'badge-neutral';
}

function formatDate(value) {
  if (!value) return '';
  try {
    return new Intl.DateTimeFormat('tr-TR', {dateStyle: 'short', timeStyle: 'short'}).format(new Date(value));
  } catch {
    return String(value);
  }
}

function renderSignature(readiness, versions, state) {
  return JSON.stringify({
    enabled: readiness.enabled,
    visible: readiness.visible,
    generationAllowed: readiness.generationAllowed,
    rollout: readiness.rollout,
    blockerCount: readiness.blockerCount,
    warningCount: readiness.warningCount,
    nextAction: readiness.nextAction,
    classification: readiness.classification,
    checks: readiness.checks,
    rows: versions.rows,
    busy: state.busy,
    message: state.message,
    error: state.error,
  });
}

function approvalSummaryHtml(approval) {
  if (!approval) return '';
  return `
    <div class="training-presentation-panel__approval" role="status">
      <div>
        <strong>${escapeHtml(approvalMethodLabel(approval.method))}</strong>
        <span>${escapeHtml(approval.approverName || 'Yetkili kullanıcı')} · ${escapeHtml(formatDate(approval.createdAt))}</span>
      </div>
      <p>${escapeHtml(approval.legalNotice)}</p>
      <small>Değişmez olay özeti: <code>${escapeHtml(approval.eventHash.slice(0, 20))}</code></small>
    </div>`;
}

function versionHistoryHtml(versions) {
  if (!versions.rows.length) {
    return '<p class="training-presentation-panel__empty">Henüz sunum sürümü oluşturulmadı.</p>';
  }
  return `
    <div class="training-presentation-panel__history" role="region" aria-label="Sunum sürüm geçmişi">
      <div class="training-presentation-panel__history-head">
        <strong>Sürüm geçmişi</strong>
        <span>${versions.count} kayıt</span>
      </div>
      <div class="training-presentation-panel__history-list">
        ${versions.rows.slice(0, 5).map((row) => `
          <article class="training-presentation-panel__version ${row === versions.latest ? 'is-latest' : ''}">
            <div>
              <strong>v${row.version} · ${escapeHtml(presentationStatusLabel(row.status))}</strong>
              <span>${escapeHtml(formatDate(row.archivedAt || row.approvedAt || row.generatedAt || row.createdAt) || 'Tarih bekleniyor')}</span>
              ${row.approval ? `<small>${escapeHtml(approvalMethodLabel(row.approval.method))} · değişmez kayıt</small>` : ''}
            </div>
            <div class="training-presentation-panel__version-files">
              ${row.pptxReady ? `<span>PPTX ${escapeHtml(formatFileSize(row.pptxSize))}</span>` : '<span>PPTX bekliyor</span>'}
              ${row.pdfReady ? `<span>PDF ${escapeHtml(formatFileSize(row.pdfSize))}</span>` : '<span>PDF bekliyor</span>'}
            </div>
          </article>`).join('')}
      </div>
    </div>`;
}

function actionButton({action, label, disabled = false, variant = 'secondary', versionId = ''}) {
  return `
    <button
      type="button"
      class="training-presentation-panel__button is-${variant}"
      data-presentation-action="${escapeHtml(action)}"
      ${versionId ? `data-version-id="${escapeHtml(versionId)}"` : ''}
      ${disabled ? 'disabled' : ''}
    >${escapeHtml(label)}</button>`;
}

function actionsHtml(readiness, versions, state) {
  const actions = presentationActionState(readiness, versions);
  const busy = Boolean(state.busy);
  const buttons = [];

  if (actions.canPreview) {
    buttons.push(actionButton({
      action: 'preview',
      label: state.busy === 'preview' ? 'Önizleme hazırlanıyor…' : 'İçerik Önizlemesi',
      disabled: busy,
    }));
  }
  if (actions.canCreateFirst) {
    buttons.push(actionButton({
      action: 'create',
      label: state.busy === 'create' ? 'Taslak oluşturuluyor…' : 'Sunum Taslağı Oluştur',
      disabled: busy,
      variant: 'primary',
    }));
  }
  if (actions.canRender && actions.latest) {
    buttons.push(actionButton({
      action: 'render',
      label: state.busy === 'render' ? 'PPTX ve PDF hazırlanıyor…' : actions.renderLabel,
      disabled: busy,
      variant: 'primary',
      versionId: actions.latest.id,
    }));
  }
  if (actions.canApprove && actions.latest) {
    buttons.push(actionButton({
      action: 'approve',
      label: 'Sunumu Onayla',
      disabled: busy,
      variant: 'primary',
      versionId: actions.latest.id,
    }));
  }
  if (actions.canDownloadPptx && actions.latest) {
    buttons.push(actionButton({
      action: 'download-pptx',
      label: state.busy === 'download-pptx' ? 'PPTX indiriliyor…' : `PPTX İndir${actions.latest.pptxSize ? ` · ${formatFileSize(actions.latest.pptxSize)}` : ''}`,
      disabled: busy,
      variant: 'download',
      versionId: actions.latest.id,
    }));
  }
  if (actions.canDownloadPdf && actions.latest) {
    buttons.push(actionButton({
      action: 'download-pdf',
      label: state.busy === 'download-pdf' ? 'PDF indiriliyor…' : `PDF İndir${actions.latest.pdfSize ? ` · ${formatFileSize(actions.latest.pdfSize)}` : ''}`,
      disabled: busy,
      variant: 'download',
      versionId: actions.latest.id,
    }));
  }
  if (actions.canArchive && actions.latest) {
    buttons.push(actionButton({
      action: 'archive',
      label: state.busy === 'archive' ? 'Arşivleniyor…' : 'Onaylı Sürümü Arşivle',
      disabled: busy,
      versionId: actions.latest.id,
    }));
  }
  if (actions.canCreateNew) {
    buttons.push(actionButton({
      action: 'create',
      label: state.busy === 'create' ? 'Yeni sürüm hazırlanıyor…' : 'Yeni Sürüm Oluştur',
      disabled: busy,
    }));
  }

  return buttons.length
    ? `<div class="training-presentation-panel__actions">${buttons.join('')}</div>`
    : '<p class="training-presentation-panel__empty">Sunum işlemleri için hazırlık kontrollerinin tamamlanması bekleniyor.</p>';
}

function renderPanel(anchor, readiness, versions) {
  removePanelsExcept(readiness.trainingId);
  let section = document.querySelector(`.${PANEL_CLASS}[data-training-id="${readiness.trainingId}"]`);
  if (!section) {
    if (!anchor?.isConnected) return;
    section = document.createElement('section');
    section.className = `panel ${PANEL_CLASS}`;
    section.dataset.trainingId = String(readiness.trainingId);
    section.setAttribute('aria-labelledby', `trainingPresentationTitle-${readiness.trainingId}`);
    section.addEventListener('click', handlePanelClick);
    anchor.insertAdjacentElement('afterend', section);
  }

  const state = getState(readiness.trainingId);
  const signature = renderSignature(readiness, versions, state);
  if (section.dataset.renderSignature === signature) return;

  const latest = versions.latest;
  const naceText = readiness.classification.naceCode
    ? `${readiness.classification.naceCode} · ${readiness.classification.naceDescription || 'NACE açıklaması'}`
    : 'Doğrulanmış NACE bilgisi bekleniyor';
  const checkItems = readiness.checks.map((check) => `
    <li class="training-presentation-panel__check">
      <span class="status-badge ${check.ok ? 'badge-ok' : 'badge-warn'}">
        ${check.ok ? 'Hazır' : 'Bekliyor'}
      </span>
      <div>
        <strong>${escapeHtml(check.label)}</strong>
        <span>${escapeHtml(check.detail)}</span>
      </div>
    </li>`).join('');
  const overallStatus = latest ? presentationStatusLabel(latest.status) : (readiness.generationAllowed ? 'Üretime hazır' : 'Hazırlık bekliyor');
  const overallClass = latest ? statusBadgeClass(latest.status) : (readiness.generationAllowed ? 'badge-ok' : 'badge-warn');

  section.innerHTML = `
    <div class="training-presentation-panel__header">
      <div>
        <h3 id="trainingPresentationTitle-${readiness.trainingId}">NACE Uyumlu Eğitim Sunumu</h3>
        <p>
          ${escapeHtml(naceText)}
          ${readiness.classification.hazardClass ? ` · ${escapeHtml(readiness.classification.hazardClass)}` : ''}
        </p>
      </div>
      <span class="status-badge ${overallClass}">${escapeHtml(overallStatus)}</span>
    </div>
    <div class="training-presentation-panel__safety-note">
      Kontrollü pilot özelliğidir. Eğitim, 20 soruluk sınav, katılım PDF'leri ve sertifikalar bu panelden bağımsız çalışır.
    </div>
    <ul class="training-presentation-panel__checks">${checkItems}</ul>
    ${state.message ? `<div class="training-presentation-panel__message is-success" role="status">${escapeHtml(state.message)}</div>` : ''}
    ${state.error ? `<div class="training-presentation-panel__message is-error" role="alert">${escapeHtml(state.error)}</div>` : ''}
    ${latest?.status === 'failed' && latest.failureDetail ? `
      <div class="training-presentation-panel__message is-error" role="alert">
        Son üretim hatası: ${escapeHtml(latest.failureDetail)}
      </div>` : ''}
    ${approvalSummaryHtml(latest?.approval)}
    ${actionsHtml(readiness, versions, state)}
    ${versionHistoryHtml(versions)}
    <p class="training-presentation-panel__next">
      <strong>Durum:</strong>
      ${readiness.blockerCount
        ? `${readiness.blockerCount} hazırlık engeli bulunuyor. ${escapeHtml(readiness.nextAction)}`
        : 'NACE, içerik sözleşmesi, üretim ve pilot erişim kontrolleri hazır.'}
      ${readiness.warningCount ? ` · ${readiness.warningCount} uzman inceleme uyarısı var.` : ''}
    </p>`;
  section.dataset.renderSignature = signature;
}

function closeDialog() {
  if (!activeDialog) return;
  activeDialog.remove();
  activeDialog = null;
  document.body.style.removeProperty('overflow');
  document.removeEventListener('keydown', dialogKeydown);
  if (dialogReturnFocus?.isConnected) dialogReturnFocus.focus();
  dialogReturnFocus = null;
}

function dialogKeydown(event) {
  if (event.key === 'Escape') closeDialog();
}

function openDialog(overlay) {
  closeDialog();
  dialogReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  document.body.appendChild(overlay);
  document.body.style.overflow = 'hidden';
  activeDialog = overlay;
  document.addEventListener('keydown', dialogKeydown);
}

function showManifestDialog(manifest) {
  const slides = Array.isArray(manifest?.slides) ? manifest.slides : [];
  const overlay = document.createElement('div');
  overlay.className = 'training-presentation-preview';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-labelledby', 'trainingPresentationPreviewTitle');
  overlay.innerHTML = `
    <div class="training-presentation-preview__card">
      <div class="training-presentation-preview__header">
        <div>
          <h3 id="trainingPresentationPreviewTitle">Sunum İçerik Önizlemesi</h3>
          <p>${slides.length} slayt · ${escapeHtml(manifest?.nace_snapshot?.nace_code || '')} · salt okunur manifest</p>
        </div>
        <button type="button" class="training-presentation-preview__close" data-preview-close aria-label="Önizlemeyi kapat">×</button>
      </div>
      <div class="training-presentation-preview__slides">
        ${slides.map((slide) => `
          <article class="training-presentation-preview__slide">
            <span>${escapeHtml(slide.position)}</span>
            <div>
              <strong>${escapeHtml(slide.title || 'Başlıksız slayt')}</strong>
              <small>${escapeHtml(String(slide.section_id || '').replaceAll('_', ' '))}${slide.approval_required ? ' · Uzman onayı gerekli' : ''}</small>
            </div>
          </article>`).join('')}
      </div>
      <div class="training-presentation-preview__footer">
        Manifest hash: <code>${escapeHtml(String(manifest?.content_hash || '').slice(0, 24))}</code>
        <span>Bu önizleme dosya üretmez ve eğitim kaydını değiştirmez.</span>
      </div>
    </div>`;
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay || event.target.closest('[data-preview-close]')) closeDialog();
  });
  openDialog(overlay);
  overlay.querySelector('[data-preview-close]')?.focus();
}

function showApprovalDialog(trainingId, version) {
  const overlay = document.createElement('div');
  overlay.className = 'training-presentation-preview training-presentation-approval-dialog';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-labelledby', 'trainingPresentationApprovalTitle');
  overlay.innerHTML = `
    <form class="training-presentation-preview__card training-presentation-approval-dialog__card">
      <div class="training-presentation-preview__header">
        <div>
          <h3 id="trainingPresentationApprovalTitle">Sunum v${escapeHtml(version.version)} Onayı</h3>
          <p>Manifest, PPTX ve PDF hash'leri onay anında değişmez olarak kilitlenir.</p>
        </div>
        <button type="button" class="training-presentation-preview__close" data-preview-close aria-label="Onay penceresini kapat">×</button>
      </div>
      <div class="training-presentation-approval-dialog__body">
        <label>
          <span>Onay yöntemi</span>
          <select name="approval_method">
            <option value="application_approval">Uygulama içi uzman onayı</option>
            <option value="qualified_esign">Doğrulanmış PAdES e-imza</option>
          </select>
        </label>
        <div class="training-presentation-approval-dialog__notice" data-approval-notice>
          Bu kayıt uygulama içi uzman onayıdır; 5070 sayılı Kanun kapsamında nitelikli elektronik imza yerine geçmez.
        </div>
        <label data-esign-field hidden>
          <span>Doğrulanmış e-imza talep numarası</span>
          <input name="esign_request_id" type="number" min="1" inputmode="numeric" placeholder="Örnek: 125" />
          <small>Talep PAdES, verified ve PDF hash'iyle birebir eşleşmiş olmalıdır.</small>
        </label>
        <label>
          <span>Onay notu (isteğe bağlı)</span>
          <textarea name="approval_note" maxlength="2000" rows="3" placeholder="İnceleme veya karar notu"></textarea>
        </label>
        <div class="training-presentation-approval-dialog__hash">
          Manifest hash: <code>${escapeHtml(version.manifestHash)}</code>
        </div>
        <div class="training-presentation-panel__message is-error" data-approval-error role="alert" hidden></div>
      </div>
      <div class="training-presentation-approval-dialog__actions">
        <button type="button" class="training-presentation-panel__button is-secondary" data-preview-close>Vazgeç</button>
        <button type="submit" class="training-presentation-panel__button is-primary">Hash'leri Kilitle ve Onayla</button>
      </div>
    </form>`;

  const form = overlay.querySelector('form');
  const method = form.querySelector('[name="approval_method"]');
  const esignField = form.querySelector('[data-esign-field]');
  const esignInput = form.querySelector('[name="esign_request_id"]');
  const notice = form.querySelector('[data-approval-notice]');
  const errorBox = form.querySelector('[data-approval-error]');
  const submit = form.querySelector('[type="submit"]');

  function syncMethod() {
    const qualified = method.value === 'qualified_esign';
    esignField.hidden = !qualified;
    esignInput.required = qualified;
    notice.textContent = qualified
      ? 'Bu yöntem yalnız doğrulanmış PAdES talebi ve sunum PDF hash eşleşmesi başarılıysa kabul edilir.'
      : 'Bu kayıt uygulama içi uzman onayıdır; 5070 sayılı Kanun kapsamında nitelikli elektronik imza yerine geçmez.';
  }
  method.addEventListener('change', syncMethod);
  syncMethod();

  overlay.addEventListener('click', (event) => {
    if (event.target === overlay || event.target.closest('[data-preview-close]')) closeDialog();
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorBox.hidden = true;
    submit.disabled = true;
    submit.textContent = 'Onay kaydediliyor…';
    setState(trainingId, {busy: 'approve', message: '', error: ''});
    const qualified = method.value === 'qualified_esign';
    const requestId = Number(esignInput.value || 0);
    try {
      await api(`/trainings/${trainingId}/presentation-versions/${version.id}/approve`, {
        method: 'POST',
        body: JSON.stringify({
          approval_method: method.value,
          confirmed_manifest_hash: version.manifestHash,
          approval_note: String(form.elements.approval_note.value || '').trim() || null,
          esign_request_id: qualified ? requestId : null,
        }),
        _retries: 0,
      });
      setState(trainingId, {
        busy: '',
        message: qualified
          ? 'Doğrulanmış PAdES e-imza onayı ve değişmez hash kaydı oluşturuldu.'
          : 'Uygulama içi uzman onayı ve değişmez hash kaydı oluşturuldu.',
        error: '',
      });
      versionsCache.delete(trainingId);
      closeDialog();
      await refreshPanel(trainingId);
    } catch (error) {
      const message = String(error?.message || error || 'Sunum onayı tamamlanamadı.');
      errorBox.textContent = message;
      errorBox.hidden = false;
      setState(trainingId, {busy: '', error: message});
      submit.disabled = false;
      submit.textContent = 'Hash\'leri Kilitle ve Onayla';
    }
  });

  openDialog(overlay);
  method.focus();
}

async function downloadWithAuth(path, filename) {
  const url = await authBlobUrl(path);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

async function loadPanelData(trainingId, {force = false} = {}) {
  if (force) {
    readinessCache.delete(trainingId);
    versionsCache.delete(trainingId);
  }
  const readinessRaw = readinessCache.has(trainingId)
    ? readinessCache.get(trainingId)
    : await api(`/trainings/${trainingId}/presentation-readiness`);
  readinessCache.set(trainingId, readinessRaw);
  const readiness = normalizePresentationReadiness(readinessRaw);
  if (!shouldRenderPresentationPanel(readiness)) {
    return {readiness, versions: normalizePresentationVersions({training_id: trainingId, rows: []})};
  }

  let versionsRaw;
  if (versionsCache.has(trainingId)) {
    versionsRaw = versionsCache.get(trainingId);
  } else {
    versionsRaw = await api(`/trainings/${trainingId}/presentation-versions`);
    versionsCache.set(trainingId, versionsRaw);
  }
  return {readiness, versions: normalizePresentationVersions(versionsRaw)};
}

async function refreshPanel(trainingId) {
  const anchor = outputPanel();
  if (!anchor || parseSavedTrainingId(anchor.textContent) !== trainingId) return;
  const data = await loadPanelData(trainingId, {force: true});
  if (shouldRenderPresentationPanel(data.readiness)) renderPanel(anchor, data.readiness, data.versions);
  else removePanelsExcept(null);
}

async function handlePanelClick(event) {
  const button = event.target.closest('[data-presentation-action]');
  if (!button || button.disabled) return;
  const panel = button.closest(`.${PANEL_CLASS}`);
  const trainingId = Number(panel?.dataset.trainingId || 0);
  const action = String(button.dataset.presentationAction || '');
  const versionId = Number(button.dataset.versionId || 0);
  if (!trainingId || !action) return;

  const cached = await loadPanelData(trainingId);
  if (action === 'approve' && cached.versions.latest) {
    showApprovalDialog(trainingId, cached.versions.latest);
    return;
  }

  setState(trainingId, {busy: action, message: '', error: ''});
  try {
    const anchor = outputPanel();
    if (anchor) renderPanel(anchor, cached.readiness, cached.versions);

    if (action === 'preview') {
      const manifest = await api(`/trainings/${trainingId}/presentation-manifest-preview`);
      showManifestDialog(manifest);
      setState(trainingId, {message: 'İçerik manifesti salt okunur olarak açıldı.'});
    } else if (action === 'create') {
      const created = await api(`/trainings/${trainingId}/presentation-versions`, {method: 'POST'});
      setState(trainingId, {message: `Sunum taslağı v${created?.version || ''} oluşturuldu. Dosya üretmek için PPTX + PDF Oluştur'a basın.`});
      versionsCache.delete(trainingId);
    } else if (action === 'render' && versionId) {
      const result = await api(`/trainings/${trainingId}/presentation-versions/${versionId}/render`, {method: 'POST', _retries: 0});
      setState(trainingId, {message: `Sunum v${result?.version || ''} hazırlandı. PPTX ve PDF dosyalarını indirebilir veya onaylayabilirsiniz.`});
      versionsCache.delete(trainingId);
    } else if (action === 'archive' && versionId) {
      const confirmed = window.confirm('Onaylı sürüm salt okunur arşive alınacak. Devam edilsin mi?');
      if (!confirmed) {
        setState(trainingId, {busy: ''});
        return;
      }
      await api(`/trainings/${trainingId}/presentation-versions/${versionId}/archive`, {method: 'POST', _retries: 0});
      setState(trainingId, {message: 'Onaylı sunum sürümü salt okunur arşive alındı.'});
      versionsCache.delete(trainingId);
    } else if (action === 'download-pptx' && versionId) {
      await downloadWithAuth(
        `/trainings/${trainingId}/presentation-versions/${versionId}/download/pptx`,
        `nace-egitim-${trainingId}-v${cached.versions.latest?.version || '1'}.pptx`,
      );
      setState(trainingId, {message: 'PPTX indirme işlemi başlatıldı.'});
    } else if (action === 'download-pdf' && versionId) {
      await downloadWithAuth(
        `/trainings/${trainingId}/presentation-versions/${versionId}/download/pdf`,
        `nace-egitim-${trainingId}-v${cached.versions.latest?.version || '1'}.pdf`,
      );
      setState(trainingId, {message: 'PDF indirme işlemi başlatıldı.'});
    }
  } catch (error) {
    setState(trainingId, {
      error: String(error?.message || error || 'Sunum işlemi tamamlanamadı.'),
    });
  } finally {
    setState(trainingId, {busy: ''});
    try {
      await refreshPanel(trainingId);
    } catch {
      const anchor = outputPanel();
      const readiness = normalizePresentationReadiness(readinessCache.get(trainingId));
      const versions = normalizePresentationVersions(versionsCache.get(trainingId));
      if (anchor && shouldRenderPresentationPanel(readiness)) renderPanel(anchor, readiness, versions);
    }
  }
}

async function attach() {
  const anchor = outputPanel();
  if (!anchor) {
    removePanelsExcept(null);
    return;
  }
  const trainingId = parseSavedTrainingId(anchor.textContent);
  if (!trainingId) {
    removePanelsExcept(null);
    return;
  }
  removePanelsExcept(trainingId);
  if (inFlight.has(trainingId)) return;

  inFlight.add(trainingId);
  try {
    const {readiness, versions} = await loadPanelData(trainingId);
    if (!shouldRenderPresentationPanel(readiness)) {
      removePanelsExcept(null);
      return;
    }
    if (anchor.isConnected) renderPanel(anchor, readiness, versions);
  } catch {
    removePanelsExcept(null);
  } finally {
    inFlight.delete(trainingId);
  }
}

function scheduleAttach() {
  window.clearTimeout(timer);
  timer = window.setTimeout(() => void attach(), 120);
}

new MutationObserver(scheduleAttach).observe(document.documentElement, {
  childList: true,
  subtree: true,
  characterData: true,
});
window.addEventListener('hashchange', scheduleAttach);
window.addEventListener('isgsuite:presentation-refresh', (event) => {
  const trainingId = Number(event?.detail?.trainingId || 0);
  if (!trainingId) return;
  versionsCache.delete(trainingId);
  readinessCache.delete(trainingId);
  setState(trainingId, {
    busy: '',
    message: 'Sunum değişiklikleri kaydedildi. Aynı eğitim kaydında yeni sürüm yüklendi.',
    error: '',
  });
  void refreshPanel(trainingId);
});
scheduleAttach();
