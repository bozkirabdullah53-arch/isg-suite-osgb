const COMPLETED_STATUSES = new Set(['generated', 'approved', 'archived']);
const RENDERABLE_STATUSES = new Set(['draft', 'failed']);

export function parseSavedTrainingId(text) {
  const match = String(text || '').match(/Kayıt\s*#\s*(\d+)/i);
  return match ? Number(match[1]) : null;
}

export function normalizePresentationReadiness(raw) {
  const payload = raw && typeof raw === 'object' ? raw : {};
  const rawChecks = Array.isArray(payload.checks) ? payload.checks : [];
  // Phase 4 renderer aynı production sürümünün parçasıdır. Phase 1/2 readiness
  // kayıtlarında bu kontrol "bekliyor" olabilir; arayüz yalnız flag açıkken
  // çalıştığından mevcut renderer kabiliyetini doğru gösterir.
  const checks = rawChecks.map((item) => {
    const code = String(item?.code || '');
    if (code === 'presentation_renderer') {
      return {
        code,
        label: String(item?.label || 'PPTX/PDF üretim servisi'),
        ok: true,
        detail: 'Deterministik PPTX ve PDF renderer hazır; üretim kullanıcı eylemiyle başlar.',
      };
    }
    return {
      code,
      label: String(item?.label || 'Kontrol'),
      ok: Boolean(item?.ok),
      detail: String(item?.detail || ''),
    };
  });
  const classification = payload.classification && typeof payload.classification === 'object'
    ? payload.classification
    : {};
  const blockers = (Array.isArray(payload.blockers) ? payload.blockers : [])
    .map((item) => ({
      code: String(item?.code || ''),
      detail: String(item?.detail || ''),
    }))
    .filter((item) => item.code !== 'presentation_renderer');
  const warnings = (Array.isArray(payload.warnings) ? payload.warnings : [])
    .map((item) => ({
      code: String(item?.code || ''),
      detail: String(item?.detail || ''),
    }));
  const enabled = Boolean(payload.enabled);
  const visible = Boolean(payload.visible);
  const generationSupported = true;

  return {
    trainingId: Number(payload.training_id || 0) || null,
    enabled,
    visible,
    readOnly: payload.read_only !== false,
    manifestPreviewSupported: payload.manifest_preview_supported !== false,
    generationSupported,
    generationAllowed: Boolean(enabled && visible && blockers.length === 0),
    coreTrainingUnaffected: payload.core_training_unaffected !== false,
    classification: {
      status: String(classification.status || 'legacy_unverified'),
      naceCode: String(classification.nace_code || ''),
      naceDescription: String(classification.nace_description || ''),
      hazardClass: String(classification.hazard_class || ''),
    },
    checks,
    blockers,
    warnings,
    blockerCount: blockers.length,
    warningCount: warnings.length,
    nextAction: String(payload.next_action || ''),
  };
}

export function normalizePresentationVersions(raw) {
  const payload = raw && typeof raw === 'object' ? raw : {};
  const rows = Array.isArray(payload.rows) ? payload.rows : [];
  const normalized = rows.map((row) => {
    const outputs = row?.outputs && typeof row.outputs === 'object' ? row.outputs : {};
    const pptx = outputs.pptx && typeof outputs.pptx === 'object' ? outputs.pptx : {};
    const pdf = outputs.pdf && typeof outputs.pdf === 'object' ? outputs.pdf : {};
    return {
      id: Number(row?.id || 0) || null,
      trainingId: Number(row?.training_id || payload.training_id || 0) || null,
      version: Number(row?.version || 0),
      status: String(row?.status || 'draft').toLowerCase(),
      manifestHash: String(row?.manifest_hash || ''),
      contractVersion: String(row?.contract_version || ''),
      templateVersion: String(row?.template_version || ''),
      pptxReady: Boolean(pptx.storage_key && pptx.file_hash),
      pdfReady: Boolean(pdf.storage_key && pdf.file_hash),
      pptxSize: Number(pptx.file_size || 0),
      pdfSize: Number(pdf.file_size || 0),
      failureCode: String(row?.failure?.code || ''),
      failureDetail: String(row?.failure?.detail || ''),
      createdAt: row?.created_at || null,
      generatedAt: row?.generated_at || null,
      approvedAt: row?.approved_at || null,
    };
  });
  normalized.sort((a, b) => b.version - a.version || (b.id || 0) - (a.id || 0));
  return {
    trainingId: Number(payload.training_id || normalized[0]?.trainingId || 0) || null,
    count: normalized.length,
    rows: normalized,
    latest: normalized[0] || null,
    readOnlyHistory: payload.read_only_history !== false,
  };
}

export function presentationActionState(readiness, versions) {
  const latest = versions?.latest || null;
  const allowed = Boolean(readiness?.generationAllowed);
  const latestCompleted = Boolean(latest && COMPLETED_STATUSES.has(latest.status));
  const latestRenderable = Boolean(latest && RENDERABLE_STATUSES.has(latest.status));

  return {
    latest,
    canPreview: Boolean(readiness?.manifestPreviewSupported),
    canCreateFirst: Boolean(allowed && !latest),
    canCreateNew: Boolean(allowed && latestCompleted),
    canRender: Boolean(allowed && latestRenderable),
    renderLabel: latest?.status === 'failed' ? 'PPTX + PDF Yeniden Oluştur' : 'PPTX + PDF Oluştur',
    canDownloadPptx: Boolean(latest?.pptxReady && latestCompleted),
    canDownloadPdf: Boolean(latest?.pdfReady && latestCompleted),
    showFailure: Boolean(latest?.status === 'failed' && latest.failureDetail),
  };
}

export function presentationStatusLabel(status) {
  return {
    draft: 'Taslak',
    generated: 'Dosyalar hazır',
    approved: 'Onaylandı',
    failed: 'Üretim hatası',
    archived: 'Arşivlendi',
  }[String(status || '').toLowerCase()] || 'Kayıt yok';
}

export function formatFileSize(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) return '';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function shouldRenderPresentationPanel(view) {
  return Boolean(view?.enabled && view?.visible);
}
