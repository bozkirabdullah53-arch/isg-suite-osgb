export const PROFESSIONAL_STATUS_LABELS = Object.freeze({
  compliant: 'Uygun',
  partially_compliant: 'Kısmen uygun',
  missing_documents: 'Belge eksik',
  expired_documents: 'Belge süresi dolmuş',
  assignment_problem: 'Görevlendirme sorunu',
  review_required: 'İnceleme gerekli',
});

export const READINESS_LABELS = Object.freeze({
  ready: 'Hazır',
  attention: 'Dikkat gerekli',
  significant: 'Önemli eksikler',
  critical: 'Kritik eksikler',
});

export function validityTone(code) {
  if (code === 'valid') return 'good';
  if (code === 'due_90') return 'info';
  if (code === 'due_60' || code === 'due_30' || code === 'missing') return 'warn';
  return 'danger';
}

export function readinessTone(status) {
  if (status === 'ready') return 'good';
  if (status === 'attention') return 'warn';
  return 'danger';
}

export function buildAuthorizedFirmQuery(filters = {}) {
  const params = new URLSearchParams();
  for (const [key, raw] of Object.entries(filters)) {
    if (raw === '' || raw == null) continue;
    params.set(key, String(raw));
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : '';
}

export function normalizeProfilePayload(form = {}) {
  const numberFields = new Set(['osgb_id', 'company_id', 'employee_count_declared']);
  const result = {};
  for (const [key, raw] of Object.entries(form)) {
    if (raw === '' || raw == null) {
      result[key] = null;
    } else if (numberFields.has(key)) {
      result[key] = Number(raw);
    } else {
      result[key] = raw;
    }
  }
  if (result.employee_count_declared != null && !Number.isFinite(result.employee_count_declared)) {
    result.employee_count_declared = null;
  }
  return result;
}

export function validateDateRange(start, end, label = 'Tarih') {
  if (!start || !end) return '';
  return end < start ? `${label} bitiş tarihi başlangıç tarihinden önce olamaz.` : '';
}

export function toggleCompletedStep(completed = [], step) {
  const current = new Set((completed || []).map(Number));
  if (current.has(Number(step))) current.delete(Number(step));
  else current.add(Number(step));
  return [...current].filter((value) => value >= 1 && value <= 11).sort((a, b) => a - b);
}
