import {describe, expect, it} from 'vitest';
import {
  formatFileSize,
  normalizePresentationReadiness,
  normalizePresentationVersions,
  parseSavedTrainingId,
  presentationActionState,
  presentationStatusLabel,
  shouldRenderPresentationPanel,
} from './training_presentation_readiness_logic';

describe('NACE training presentation readiness logic', () => {
  it('extracts the persisted training id from the existing output panel text', () => {
    expect(parseSavedTrainingId('Kayıt #101 · 2 katılımcı üzerinden PDF çıktıları hazır.')).toBe(101);
    expect(parseSavedTrainingId('Kayıt bulunamadı')).toBeNull();
  });

  it('keeps the optional panel hidden while the feature flag is disabled', () => {
    const view = normalizePresentationReadiness({
      training_id: 101,
      enabled: false,
      visible: false,
      read_only: true,
      core_training_unaffected: true,
    });
    expect(view.trainingId).toBe(101);
    expect(view.readOnly).toBe(true);
    expect(view.coreTrainingUnaffected).toBe(true);
    expect(shouldRenderPresentationPanel(view)).toBe(false);
    expect(view.generationAllowed).toBe(false);
  });

  it('recognizes the Phase 4 renderer and keeps real blockers', () => {
    const view = normalizePresentationReadiness({
      training_id: 101,
      enabled: true,
      visible: true,
      manifest_preview_supported: true,
      core_training_unaffected: true,
      classification: {
        status: 'verified',
        nace_code: '62.01.01',
        nace_description: 'Bilgisayar programlama faaliyetleri',
        hazard_class: 'Az Tehlikeli',
      },
      checks: [
        {code: 'verified_nace_snapshot', label: 'Doğrulanmış NACE snapshot', ok: true, detail: 'Hazır'},
        {code: 'template_contract', label: 'Uzman onaylı sunum şablonu', ok: true, detail: 'Hazır'},
        {code: 'presentation_renderer', label: 'PPTX/PDF üretim servisi', ok: false, detail: 'Eski readiness'},
      ],
      blockers: [{code: 'presentation_renderer', detail: 'Eski readiness'}],
      warnings: [],
    });

    expect(shouldRenderPresentationPanel(view)).toBe(true);
    expect(view.classification.naceCode).toBe('62.01.01');
    expect(view.checks.find((item) => item.code === 'presentation_renderer')?.ok).toBe(true);
    expect(view.blockerCount).toBe(0);
    expect(view.generationSupported).toBe(true);
    expect(view.generationAllowed).toBe(true);
  });

  it('does not hide verified-NACE or topic blockers', () => {
    const view = normalizePresentationReadiness({
      training_id: 101,
      enabled: true,
      visible: true,
      checks: [
        {code: 'verified_nace_snapshot', label: 'NACE', ok: false, detail: 'Eksik'},
        {code: 'presentation_renderer', label: 'Renderer', ok: false, detail: 'Eski readiness'},
      ],
      blockers: [
        {code: 'verified_nace_snapshot', detail: 'Eksik'},
        {code: 'presentation_renderer', detail: 'Eski readiness'},
      ],
    });
    expect(view.blockerCount).toBe(1);
    expect(view.blockers[0].code).toBe('verified_nace_snapshot');
    expect(view.generationAllowed).toBe(false);
  });
});

describe('NACE presentation version actions', () => {
  const readiness = normalizePresentationReadiness({
    training_id: 101,
    enabled: true,
    visible: true,
    manifest_preview_supported: true,
    blockers: [{code: 'presentation_renderer'}],
    checks: [{code: 'presentation_renderer', label: 'Renderer', ok: false}],
  });

  it('allows the first draft only when no version exists', () => {
    const versions = normalizePresentationVersions({training_id: 101, rows: []});
    const actions = presentationActionState(readiness, versions);
    expect(actions.canPreview).toBe(true);
    expect(actions.canCreateFirst).toBe(true);
    expect(actions.canRender).toBe(false);
    expect(actions.canCreateNew).toBe(false);
  });

  it('allows rendering for draft and failed versions', () => {
    const draft = normalizePresentationVersions({
      training_id: 101,
      rows: [{id: 1, training_id: 101, version: 1, status: 'draft', outputs: {}}],
    });
    expect(presentationActionState(readiness, draft).canRender).toBe(true);
    expect(presentationActionState(readiness, draft).renderLabel).toBe('PPTX + PDF Oluştur');

    const failed = normalizePresentationVersions({
      training_id: 101,
      rows: [{
        id: 2,
        training_id: 101,
        version: 2,
        status: 'failed',
        failure: {detail: 'Depolama hatası'},
        outputs: {},
      }],
    });
    const actions = presentationActionState(readiness, failed);
    expect(actions.canRender).toBe(true);
    expect(actions.renderLabel).toBe('PPTX + PDF Yeniden Oluştur');
    expect(actions.showFailure).toBe(true);
  });

  it('allows downloads and a new version after successful generation', () => {
    const versions = normalizePresentationVersions({
      training_id: 101,
      rows: [
        {
          id: 9,
          training_id: 101,
          version: 3,
          status: 'generated',
          manifest_hash: 'a'.repeat(64),
          outputs: {
            pptx: {storage_key: 'a.pptx', file_hash: 'b'.repeat(64), file_size: 1048576},
            pdf: {storage_key: 'a.pdf', file_hash: 'c'.repeat(64), file_size: 2048},
          },
        },
        {id: 7, training_id: 101, version: 2, status: 'archived', outputs: {}},
      ],
    });
    expect(versions.latest.version).toBe(3);
    const actions = presentationActionState(readiness, versions);
    expect(actions.canDownloadPptx).toBe(true);
    expect(actions.canDownloadPdf).toBe(true);
    expect(actions.canCreateNew).toBe(true);
    expect(actions.canRender).toBe(false);
    expect(formatFileSize(1048576)).toBe('1.0 MB');
    expect(formatFileSize(2048)).toBe('2 KB');
  });

  it('uses clear Turkish status labels', () => {
    expect(presentationStatusLabel('draft')).toBe('Taslak');
    expect(presentationStatusLabel('generated')).toBe('Dosyalar hazır');
    expect(presentationStatusLabel('failed')).toBe('Üretim hatası');
    expect(presentationStatusLabel('unknown')).toBe('Kayıt yok');
  });
});
