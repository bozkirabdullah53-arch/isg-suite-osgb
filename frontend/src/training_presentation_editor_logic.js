export const PRESENTATION_SECTION_LABELS = Object.freeze({
  cover: 'Açılış',
  learning_objectives: 'Öğrenme hedefleri',
  legal_basis: 'Mevzuat ve sorumluluklar',
  nace_identity: 'NACE ve işyeri faaliyeti',
  training_plan: 'Eğitim planı',
  foundation_ohs: 'Temel İSG konuları',
  work_specific_topics: 'İşe ve işyerine özgü riskler',
  technical_risks: 'Teknik riskler',
  control_measures: 'Kontrol tedbirleri',
  ppe: 'Kişisel koruyucu donanım',
  emergency: 'Acil durum',
  assessment: 'Ölçme ve değerlendirme',
  summary: 'Özet',
  sources_and_version: 'Kaynaklar ve sürüm',
  custom_instructor_slide: 'Eğitmen tarafından eklenen içerik',
});

export function presentationSectionLabel(sectionId) {
  return PRESENTATION_SECTION_LABELS[String(sectionId || '').trim()] || 'Eğitim içeriği';
}

export const PRESENTATION_EDITOR_ROLES = new Set([
  'global_admin',
  'company_admin',
  'safety_specialist',
  'workplace_physician',
]);

export function canEditPresentationRole(role) {
  return PRESENTATION_EDITOR_ROLES.has(String(role || '').toLowerCase());
}

export function lessonPointsFromText(value) {
  return String(value || '')
    .split(/\r?\n/)
    .map((row) => row.replace(/^\s*[-•\d.)]+\s*/, '').trim())
    .filter(Boolean)
    .slice(0, 8);
}

export function pickEditableVersion(rows) {
  const list = Array.isArray(rows) ? rows : [];
  return [...list]
    .filter((row) => row?.id && ['draft', 'generated', 'approved', 'failed', 'archived'].includes(String(row.status || '').toLowerCase()))
    .sort((a, b) => Number(b.version || 0) - Number(a.version || 0))[0] || null;
}

export function editorSlides(manifest) {
  return (Array.isArray(manifest?.slides) ? manifest.slides : [])
    .map((slide) => ({
      position: Number(slide.position || 0),
      title: String(slide.title || 'Başlıksız slayt'),
      sectionId: String(slide.section_id || ''),
      sectionLabel: presentationSectionLabel(slide.section_id),
      approvalRequired: Boolean(slide.approval_required),
    }))
    .filter((slide) => slide.position > 0)
    .sort((a, b) => a.position - b.position);
}

export function buildPresentationEditPayload(form, {newSlide = false} = {}) {
  const common = {
    title: String(form?.title || '').trim() || undefined,
    lesson_points: lessonPointsFromText(form?.lessonPoints),
    scenario: String(form?.scenario || '').trim() || undefined,
    key_takeaway: String(form?.keyTakeaway || '').trim() || undefined,
    instructor_note: String(form?.instructorNote || '').trim() || undefined,
  };
  const hasContent = common.lesson_points.length || common.scenario || common.key_takeaway || common.instructor_note;
  if (!hasContent) throw new Error('En az bir ders maddesi, vaka, ana mesaj veya eğitmen notu girin.');
  if (newSlide) {
    if (!common.title) throw new Error('Yeni slayt için başlık zorunludur.');
    return {
      slide_updates: [],
      append_slides: [common],
      change_note: String(form?.changeNote || '').trim() || undefined,
      auto_enrich_teaching_v3: form?.autoEnrich !== false,
    };
  }
  const position = Number(form?.position || 0);
  if (!Number.isInteger(position) || position < 1) throw new Error('Düzenlenecek slaytı seçin.');
  return {
    slide_updates: [{
      position,
      title: common.title,
      mode: form?.mode === 'replace' ? 'replace' : 'append',
      lesson_points: common.lesson_points,
      scenario: common.scenario,
      key_takeaway: common.key_takeaway,
      instructor_note: common.instructor_note,
    }],
    append_slides: [],
    change_note: String(form?.changeNote || '').trim() || undefined,
    auto_enrich_teaching_v3: form?.autoEnrich !== false,
  };
}
