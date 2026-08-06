export function parseSavedTrainingId(text) {
  const match = String(text || '').match(/Kayıt\s*#\s*(\d+)/i);
  return match ? Number(match[1]) : null;
}

export function normalizePresentationReadiness(raw) {
  const payload = raw && typeof raw === 'object' ? raw : {};
  const checks = Array.isArray(payload.checks)
    ? payload.checks.map((item) => ({
        code: String(item?.code || ''),
        label: String(item?.label || 'Kontrol'),
        ok: Boolean(item?.ok),
        detail: String(item?.detail || ''),
      }))
    : [];
  const classification = payload.classification && typeof payload.classification === 'object'
    ? payload.classification
    : {};

  return {
    trainingId: Number(payload.training_id || 0) || null,
    enabled: Boolean(payload.enabled),
    visible: Boolean(payload.visible),
    readOnly: payload.read_only !== false,
    generationSupported: Boolean(payload.generation_supported),
    generationAllowed: Boolean(payload.generation_allowed),
    coreTrainingUnaffected: payload.core_training_unaffected !== false,
    classification: {
      status: String(classification.status || 'legacy_unverified'),
      naceCode: String(classification.nace_code || ''),
      naceDescription: String(classification.nace_description || ''),
      hazardClass: String(classification.hazard_class || ''),
    },
    checks,
    blockerCount: Array.isArray(payload.blockers) ? payload.blockers.length : 0,
    warningCount: Array.isArray(payload.warnings) ? payload.warnings.length : 0,
    nextAction: String(payload.next_action || ''),
  };
}

export function shouldRenderPresentationPanel(view) {
  return Boolean(view?.enabled && view?.visible);
}
