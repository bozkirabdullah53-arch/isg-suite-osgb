export const TRACEABILITY_VERSION = 'presentation-question-traceability-v1';
export const INSTRUCTOR_UI_V2 = 'instructor-mode-v2';

function clean(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim();
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
    return block.value ? [`${label}: ${clean(block.value)}`] : [];
  }
  if (type === 'frozen_training_topic') return block.value ? [clean(block.value)] : [];
  if (type === 'technical_risk_tag') return block.value ? [`Teknik risk: ${clean(block.value).replaceAll('_', ' ')}`] : [];
  if (type === 'special_risk') return block.value ? [`Özel risk: ${clean(block.value).replaceAll('_', ' ')}`] : [];
  if (type === 'control_hierarchy') {
    return [
      'Kontrol sırası: tehlikeyi ortadan kaldır/azalt, mühendislik ve toplu korunmayı uygula, organizasyon tedbirlerini tamamla, kalan risk için KKD kullan.',
    ];
  }
  if (type === 'topic_summary') return (block.values || []).map((value) => `Konu: ${clean(value)}`).filter(Boolean);
  if (type === 'risk_summary') return (block.values || []).map((value) => `Risk: ${clean(value).replaceAll('_', ' ')}`).filter(Boolean);
  if (type === 'nace_identity') {
    return [block.nace_code ? `NACE: ${clean(block.nace_code)}` : '', clean(block.nace_description)].filter(Boolean);
  }
  if (type === 'hazard_class') return block.value ? [`Tehlike sınıfı: ${clean(block.value)}`] : [];
  if (type === 'exam_distribution') return [`Sınav kapsamı: ${Number(block.foundation || 0)} temel + ${Number(block.work_specific || 0)} işe özgü soru`];
  if (block.value !== undefined && block.value !== null && clean(block.value)) {
    return [`${clean(type).replaceAll('_', ' ')}: ${clean(block.value)}`];
  }
  return [];
}

export function instructorBulletPresentation(item) {
  const value = clean(item);
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
    return {
      position: Number(slide.position || 0),
      title: clean(slide.title) || 'Başlıksız slayt',
      sectionId: clean(slide.section_id),
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
    naceDescription: clean(manifest.nace_snapshot?.nace_description),
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
