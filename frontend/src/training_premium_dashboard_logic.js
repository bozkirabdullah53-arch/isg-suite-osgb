export const DASHBOARD_TAB_LABELS = {
  temel: 'Temel İSG Eğitimi',
  yenileme: 'Yenileme Takibi',
  kayitlar: 'Kayıtlar',
};

export function normalizeTrainingDashboard(raw) {
  const data = raw && typeof raw === 'object' ? raw : {};
  return {
    enabled: Boolean(data.enabled),
    companyId: Number(data.company_id || 0) || null,
    today: data.today || null,
    trackingFrom: data.work_start_tracking_from || null,
    summary: data.summary && typeof data.summary === 'object' ? data.summary : {},
    actions: Array.isArray(data.actions) ? data.actions : [],
    rows: Array.isArray(data.rows) ? data.rows : [],
    safety: data.safety && typeof data.safety === 'object' ? data.safety : {},
  };
}

export function dashboardHeadline(summary = {}) {
  const danger = Number(summary.work_start_missing || 0) + Number(summary.basic_overdue || 0);
  const warning = Number(summary.work_start_pending || 0)
    + Number(summary.basic_waiting || 0)
    + Number(summary.basic_due_soon || 0)
    + Number(summary.result_pending || 0);
  if (danger > 0) return {tone: 'danger', label: `${danger} öncelikli işlem var`};
  if (warning > 0) return {tone: 'warning', label: `${warning} işlem bekliyor`};
  return {tone: 'ok', label: 'Acil eğitim işlemi görünmüyor'};
}

export function statusTone(value) {
  return ['danger', 'warning', 'ok', 'neutral', 'info'].includes(value) ? value : 'neutral';
}

export function actionTargetLabel(target) {
  return DASHBOARD_TAB_LABELS[target] || 'Eğitimler';
}
