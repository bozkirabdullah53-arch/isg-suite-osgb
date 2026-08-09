export const TRACEABILITY_VERSION = 'presentation-question-traceability-v1';
export const INSTRUCTOR_UI_V2 = 'instructor-mode-v2';

function clean(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim();
}

const LEGAL_BASIS_POINTS = Object.freeze([
  'İşyerindeki tehlikeleri ve size bildirilen kontrol tedbirlerini öğrenin.',
  'Verilen eğitim, talimat ve güvenli çalışma kurallarına uygun hareket edin.',
  'Güvensiz durumu, ramak kala olayı, iş kazasını veya sağlık belirtisini gecikmeden bildirin.',
  'Ciddi ve yakın tehlikede güvenli biçimde işi durdurun, tehlikeli alandan uzaklaşın ve yetkiliye haber verin.',
]);

const BLOCK_TYPE_LABELS = Object.freeze({
  training_date: 'Eğitim tarihi',
  training_duration: 'Eğitim süresi',
  training_location: 'Eğitim yeri',
  trainer: 'Eğitmen',
  instructor: 'Eğitmen',
  learning_objective: 'Öğrenme hedefi',
  learning_objectives: 'Öğrenme hedefleri',
  target_group: 'Hedef grup',
  audience: 'Hedef grup',
});

const USER_VISIBLE_PHRASES = Object.freeze([
  [/\btraining date\b/giu, 'Eğitim tarihi'],
  [/\btraining duration\b/giu, 'Eğitim süresi'],
  [/\btraining location\b/giu, 'Eğitim yeri'],
  [/\blearning objective\b/giu, 'Öğrenme hedefi'],
  [/\blesson explanation\b/giu, 'Ders anlatımı'],
  [/\bcase scenario\b/giu, 'Vaka çalışması'],
  [/\bkey takeaway\b/giu, 'Ana mesaj'],
  [/\bcheck question\b/giu, 'Kontrol sorusu'],
  [/\bcontrol measures?\b/giu, 'Kontrol tedbirleri'],
  [/\bsafe behavior\b/giu, 'Güvenli davranış'],
  [/\bofficial source\b/giu, 'Resmî kaynak'],
  [/\blearning objectives?\b/giu, 'Öğrenme hedefleri'],
  [/\bpersonal protective equipment\b/giu, 'kişisel koruyucu donanım (KKD)'],
  [/\bmanual handling\b/giu, 'elle taşıma'],
  [/\bbattery charging\b/giu, 'akü şarjı'],
  [/\bemergency exit\b/giu, 'acil çıkış'],
  [/\bbiological agents?\b/giu, 'biyolojik etkenler'],
  [/\bmedical waste\b/giu, 'tıbbi atık'],
  [/\bpatient handling\b/giu, 'hasta taşıma'],
  [/\bfalling loads?\b/giu, 'düşen yükler'],
  [/\bloading ramp\b/giu, 'yükleme rampası'],
  [/\bvehicle restraint\b/giu, 'araç sabitleme'],
  [/\bsharps\b/giu, 'kesici-delici aletler'],
]);

export function localizeInstructorText(value) {
  let text = clean(value);
  for (const [pattern, replacement] of USER_VISIBLE_PHRASES) {
    text = text.replace(pattern, replacement);
  }
  return text;
}

function blockBullets(block) {
  if (!block || typeof block !== 'object') return [];
  const type = clean(block.type);
  if (['tehlike', 'kontrol_tedbiri', 'guvenli_davranis'].includes(type)) {
    const label = {
      tehlike: 'Tehlike',
      kontrol_tedbiri: 'Kontrol tedbiri',
      guvenli_davranis: 'Güvenli davranış',
    }[type];
    return block.value ? [`${label}: ${localizeInstructorText(block.value)}`] : [];
  }
  if (type === 'frozen_training_topic') return block.value ? [localizeInstructorText(block.value)] : [];
  if (type === 'technical_risk_tag') return block.value ? [`Teknik risk: ${localizeInstructorText(block.value).replaceAll('_', ' ')}`] : [];
  if (type === 'special_risk') return block.value ? [`Özel risk: ${localizeInstructorText(block.value).replaceAll('_', ' ')}`] : [];
  if (type === 'control_hierarchy') {
    return [
      'Kontrol sırası: tehlikeyi ortadan kaldır/azalt, mühendislik ve toplu korunmayı uygula, organizasyon tedbirlerini tamamla, kalan risk için KKD kullan.',
    ];
  }
  if (type === 'topic_summary') return (block.values || []).map((value) => `Konu: ${localizeInstructorText(value)}`).filter(Boolean);
  if (type === 'risk_summary') return (block.values || []).map((value) => `Risk: ${localizeInstructorText(value).replaceAll('_', ' ')}`).filter(Boolean);
  if (type === 'nace_identity') {
    return [block.nace_code ? `NACE: ${clean(block.nace_code)}` : '', localizeInstructorText(block.nace_description)].filter(Boolean);
  }
  if (type === 'hazard_class') return block.value ? [`Tehlike sınıfı: ${localizeInstructorText(block.value)}`] : [];
  if (type === 'exam_distribution') return [`Sınav kapsamı: ${Number(block.foundation || 0)} temel + ${Number(block.work_specific || 0)} işe özgü soru`];
  if (block.value !== undefined && block.value !== null && clean(block.value)) {
    const label = BLOCK_TYPE_LABELS[type] || 'Eğitim bilgisi';
    return [`${label}: ${localizeInstructorText(block.value)}`];
  }
  return [];
}

export function instructorBulletPresentation(item) {
  const value = localizeInstructorText(item);
  const lowered = value.toLocaleLowerCase('tr-TR');
  const definitions = [
    ['tehlike:', 'hazard', 'Tehlike'],
    ['kontrol tedbiri:', 'control', 'Kontrol tedbiri'],
    ['güvenli davranış:', 'behavior', 'Güvenli davranış'],
    ['teknik risk:', 'risk', 'Teknik risk'],
    ['özel risk:', 'risk', 'Özel risk'],
    ['kontrol sırası:', 'hierarchy', 'Kontrol hiyerarşisi'],
    ['nace:', 'identity', 'NACE'],
    ['tehlike sınıfı:', 'identity', 'Tehlike sınıfı'],
    ['sınav kapsamı:', 'assessment', 'Sınav kapsamı'],
    ['konu:', 'context', 'Konu'],
    ['risk:', 'risk', 'Risk'],
    ['eğitim tarihi:', 'context', 'Eğitim tarihi'],
    ['eğitim süresi:', 'context', 'Eğitim süresi'],
    ['eğitim yeri:', 'context', 'Eğitim yeri'],
  ];
  for (const [prefix, kind, label] of definitions) {
    if (lowered.startsWith(prefix)) {
      return {kind, label, text: value.slice(prefix.length).trim()};
    }
  }
  return {kind: 'context', label: 'Eğitim notu', text: value};
}

export function normalizeInstructorManifest(manifest) {
  if (!manifest || typeof manifest !== 'object') throw new Error('Sunum manifesti bulunamadı.');
  const traceability = manifest.traceability || {};
  const coverage = traceability.coverage || {};
  if (traceability.version !== TRACEABILITY_VERSION) {
    throw new Error('Bu sunum sürümü Eğitmen Modu için 20/20 izlenebilirlik taşımıyor. Yeni sürüm oluşturun.');
  }
  if (
    Number(coverage.question_total) !== 20 ||
    Number(coverage.linked_questions) !== 20 ||
    Number(coverage.source_linked_questions) !== 20 ||
    Number(coverage.orphan_questions) !== 0 ||
    coverage.cross_sector_fallback === true ||
    coverage.status !== 'passed'
  ) {
    throw new Error('Sunumun soru-slayt kapsam doğrulaması başarısız.');
  }
  const links = Array.isArray(traceability.question_links) ? traceability.question_links : [];
  const linkCountBySlide = new Map();
  for (const link of links) {
    for (const position of link.slide_positions || []) {
      linkCountBySlide.set(Number(position), (linkCountBySlide.get(Number(position)) || 0) + 1);
    }
  }
  const slides = (Array.isArray(manifest.slides) ? manifest.slides : []).map((slide) => {
    const bullets = [];
    for (const block of slide.content_blocks || []) {
      for (const item of blockBullets(block)) {
        if (item && !bullets.includes(item)) bullets.push(item);
      }
    }
    const sectionId = clean(slide.section_id);
    if (sectionId === 'legal_basis' && !bullets.length) {
      bullets.push(...LEGAL_BASIS_POINTS);
    }
    return {
      position: Number(slide.position || 0),
      title: localizeInstructorText(slide.title) || 'Başlıksız slayt',
      sectionId,
      bullets,
      sources: Array.from(new Set((slide.source_refs || []).map(clean).filter(Boolean))),
      approvalRequired: Boolean(slide.approval_required),
      linkedQuestionCount: linkCountBySlide.get(Number(slide.position || 0)) || 0,
    };
  });
  if (!slides.length || slides.some((slide, index) => slide.position !== index + 1)) {
    throw new Error('Sunum slayt sırası geçersiz.');
  }
  return {
    manifestHash: clean(manifest.content_hash),
    naceCode: clean(manifest.nace_snapshot?.nace_code),
    naceDescription: localizeInstructorText(manifest.nace_snapshot?.nace_description),
    slideCount: slides.length,
    uiVersion: clean(manifest.rendering?.instructor_mode_ui) || 'instructor-mode-v1',
    coverageV2: manifest.coverage_v2 && typeof manifest.coverage_v2 === 'object' ? manifest.coverage_v2 : null,
    coverage: {
      total: 20,
      linked: 20,
      sourced: 20,
      orphan: 0,
    },
    slides,
  };
}

export function playerIndexForKey(key, index, total) {
  const last = Math.max(0, Number(total || 1) - 1);
  if (['ArrowRight', 'PageDown', ' '].includes(key)) return Math.min(last, index + 1);
  if (['ArrowLeft', 'PageUp'].includes(key)) return Math.max(0, index - 1);
  if (key === 'Home') return 0;
  if (key === 'End') return last;
  return index;
}
