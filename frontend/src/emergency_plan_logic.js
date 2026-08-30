export const EMERGENCY_SCENARIOS = [
  {code: 'yangin', label: 'Yangın'},
  {code: 'patlama', label: 'Patlama / parlama'},
  {code: 'chemical_release', label: 'Tehlikeli kimyasal yayılımı / sızıntı'},
  {code: 'biological', label: 'Biyolojik etken / salgın'},
  {code: 'natural_disaster', label: 'Deprem / doğal afet'},
  {code: 'flood_storm', label: 'Sel / fırtına / yıldırım'},
  {code: 'sabotage', label: 'Sabotaj / şiddet / güvenlik olayı'},
  {code: 'work_accident', label: 'İş kazası / tıbbi acil durum'},
  {code: 'power_gas', label: 'Elektrik / gaz acil durumu'},
  {code: 'other', label: 'Diğer'},
];

export const DEFAULT_PLAN_DETAILS = {
  version: 1,
  emergency_types: [],
  preventive_measures: '',
  measurement_evaluation: '',
  equipment_inventory: '',
  response_methods: '',
  special_risk_mode: 'not_evaluated',
  special_risk_areas: '',
  energy_controls_mode: 'not_evaluated',
  energy_shutoff_points: '',
  special_groups: '',
  visitors_included: true,
  temporary_workers_included: true,
  shared_workplace: false,
  shared_workplace_note: '',
  approval_status: 'not_confirmed',
  posted_confirmed: false,
  employees_informed: false,
  last_drill_date: '',
  next_drill_date: '',
  drill_record_ref: '',
  external_contacts: [{name: '112 Acil Çağrı Merkezi', phone: '112', note: 'Ulusal acil çağrı'}],
};

export function localDateString(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function addYears(value, years) {
  const base = value ? new Date(`${value}T12:00:00`) : new Date();
  if (Number.isNaN(base.getTime())) return '';
  base.setFullYear(base.getFullYear() + Number(years || 0));
  return localDateString(base);
}

export function reviewYearsForHazard(hazardClass) {
  const value = String(hazardClass || '').toLowerCase();
  if (value.includes('cok') || value.includes('çok') || value.includes('heavy')) return 2;
  if (value.includes('tehlikeli') && !value.includes('az')) return 4;
  return 6;
}

export function createEmptyPlan({companyId = '', hazardClass = '', today = localDateString()} = {}) {
  return {
    company_id: companyId || '',
    title: 'Acil Durum Planı',
    revision_no: '00',
    plan_date: today,
    next_review_date: addYears(today, reviewYearsForHazard(hazardClass)),
    assembly_areas: '',
    scenario_summary: '',
    notes: '',
    details: cloneDetails(),
  };
}

export function cloneDetails(raw = {}) {
  const source = raw && typeof raw === 'object' ? raw : {};
  const contacts = Array.isArray(source.external_contacts)
    ? source.external_contacts.map((item) => ({
      name: String(item?.name || ''),
      phone: String(item?.phone || ''),
      note: String(item?.note || ''),
    }))
    : DEFAULT_PLAN_DETAILS.external_contacts.map((item) => ({...item}));
  return {
    ...DEFAULT_PLAN_DETAILS,
    ...source,
    emergency_types: Array.isArray(source.emergency_types) ? [...new Set(source.emergency_types.map(String))] : [],
    external_contacts: contacts,
  };
}

export function planFormFromRow(row, company) {
  const fallback = createEmptyPlan({
    companyId: row?.company_id || company?.id || '',
    hazardClass: company?.hazard_class,
    today: row?.plan_date || localDateString(),
  });
  return {
    ...fallback,
    ...row,
    company_id: row?.company_id || company?.id || '',
    plan_date: row?.plan_date || '',
    next_review_date: row?.next_review_date || '',
    details: cloneDetails(row?.details),
  };
}

export function scenarioLabel(code) {
  return EMERGENCY_SCENARIOS.find((item) => item.code === code)?.label || code || 'Diğer';
}

export function formatPlanDate(value) {
  if (!value) return '—';
  const parsed = new Date(`${value}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat('tr-TR', {day: '2-digit', month: 'short', year: 'numeric'}).format(parsed);
}

export function getReadiness(row) {
  if (row?.compliance && typeof row.compliance === 'object' && Array.isArray(row.compliance.checks)) {
    return row.compliance;
  }
  const checks = [
    {id: 'plan_dates', label: 'Plan tarihleri', status: row?.plan_date && row?.next_review_date ? 'ok' : 'error', detail: 'Plan ve gözden geçirme tarihi'},
    {id: 'evacuation_map', label: 'Tahliye krokisi', status: row?.has_scene ? 'ok' : 'error', detail: 'Kat krokisi ve işaretler'},
    {id: 'assembly', label: 'Toplanma alanı', status: row?.assembly_areas ? 'ok' : 'error', detail: 'Toplanma alanı'},
  ];
  const passed = checks.filter((item) => item.status === 'ok').length;
  return {
    pct: Math.round((passed / checks.length) * 100),
    status: passed === checks.length ? 'ready' : 'action',
    label: passed === checks.length ? 'Hazır' : 'İyileştirme gerekli',
    checks,
    missing: checks.filter((item) => item.status !== 'ok').map((item) => item.detail),
    required_passed: passed,
    required_total: checks.length,
    summary: `${passed}/${checks.length} temel kontrol tamamlandı.`,
  };
}

export function readinessTone(readiness) {
  if (readiness?.status === 'ready') return 'ready';
  if (readiness?.status === 'review') return 'review';
  if (readiness?.status === 'draft') return 'draft';
  return 'action';
}
