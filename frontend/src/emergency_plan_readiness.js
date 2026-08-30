/**
 * Acil durum planının dijital hazırlık sinyallerini tek yerde üretir.
 * Bu skor hukuki uygunluk kararı değildir; uzman saha doğrulamasına hazırlık
 * için eksik kanıtları görünür kılar.
 */
export function buildEmergencyPlanReadiness(row, insight = {}) {
  const checks = [
    {label: 'Plan tarihi', ok: Boolean(row?.plan_date)},
    {label: 'Gözden geçirme', ok: Boolean(row?.next_review_date)},
    {label: 'Toplanma alanı', ok: Boolean(row?.assembly_areas?.trim())},
    {label: 'Senaryo özeti', ok: Boolean(row?.scenario_summary?.trim())},
    {label: 'Kat krokisi', ok: Boolean(row?.has_scene)},
    {label: 'Acil çıkış', ok: Number(insight?.checks?.exit || 0) > 0},
    {label: 'Acil ekip kadrosu', ok: Boolean(insight?.team_readiness?.ready)},
    {label: 'Tamamlanmış tatbikat', ok: insight?.drill_readiness?.status === 'current'},
  ];
  const complete = checks.filter((item) => item.ok).length;
  return {
    checks,
    complete,
    total: checks.length,
    percent: Math.round((complete / checks.length) * 100),
    attention: row?.review_status === 'overdue' || complete < checks.length,
  };
}
