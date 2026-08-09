export const PREMIUM_TRAINING_TYPES = [
  {value: 'İşe Başlama Eğitimi', label: 'İşe Başlama Eğitimi · en az 2 saat · yüz yüze'},
  {value: 'Bilgi Yenileme Eğitimi', label: 'Bilgi Yenileme Eğitimi · işe özgü riskler'},
];

export const LIFECYCLE_STEPS = [
  {id: 'planned', label: '1. Planla'},
  {id: 'deliver', label: '2. Eğitimi Gerçekleştir'},
  {id: 'results', label: '3. Katılım / Sonuç'},
  {id: 'documents', label: '4. Belge ve Arşiv'},
];

export function normalizePremiumPolicy(raw) {
  const policy = raw && typeof raw === 'object' ? raw : {};
  return {
    enabled: Boolean(policy.enabled),
    version: String(policy.version || ''),
    cutover: policy.cutover || null,
    checkedAt: policy.checked_at || null,
    officialSource: policy.official_source || null,
    rules: policy.rules || {},
  };
}

export function parseTrainingIdFromText(text) {
  const source = String(text || '');
  const certificate = source.match(/EGT-(\d{6})-\d{6}/i);
  if (certificate) return Number(certificate[1]);
  const explicit = source.match(/Kayıt\s*#(\d+)/i);
  return explicit ? Number(explicit[1]) : null;
}

export function lifecycleTone(stage) {
  if (stage === 'document_ready' || stage === 'record_ready') return 'ready';
  if (stage === 'cancelled') return 'danger';
  if (stage === 'attendance_pending' || stage === 'results_pending') return 'warning';
  return 'info';
}

export function ruleSummary(policy, hazardClass) {
  const rules = normalizePremiumPolicy(policy).rules;
  const initial = rules.initial_basic?.hours?.[hazardClass];
  const repeat = rules.repeat_basic?.hours?.[hazardClass];
  const workSpecific = rules.work_specific?.hours?.[hazardClass];
  return {
    initialHours: Number(initial || 0),
    repeatHours: Number(repeat || 0),
    workSpecificHours: Number(workSpecific || 0),
    lessonDefinition: rules.lesson_definition || '45 dakika ders + 15 dakika ara dinlenmesi',
  };
}

export function shouldReplacePrematureVerification(policy) {
  return normalizePremiumPolicy(policy).enabled;
}

export function outputActionPolicy(lifecycle) {
  const state = lifecycle && typeof lifecycle === 'object' ? lifecycle : {};
  const kind = String(state.policy?.kind || '');
  if (!state.premium_enforced || !['work_start', 'information_refresh'].includes(kind)) {
    return {
      certificateAllowed: true,
      examAllowed: true,
      attendanceAllowed: true,
      attendanceLabel: 'Katılım PDF (İmza Formu)',
      note: '',
    };
  }
  if (kind === 'information_refresh') {
    return {
      certificateAllowed: false,
      examAllowed: false,
      attendanceAllowed: true,
      attendanceLabel: 'Bilgi Yenileme Eğitimi Tutanağı PDF',
      note: 'Bilgi Yenileme Eğitimi, düzenli Temel İSG tekrar eğitimi değildir. Temel İSG sınavı ve sertifikası bu kayıtta oluşturulmaz.',
    };
  }
  return {
    certificateAllowed: false,
    examAllowed: false,
    attendanceAllowed: true,
    attendanceLabel: 'İşe Başlama Eğitimi Tutanağı PDF',
    note: 'İşe Başlama Eğitimi, Temel İSG Eğitimi değildir. Temel İSG sınavı ve sertifikası bu kayıtta oluşturulmaz.',
  };
}