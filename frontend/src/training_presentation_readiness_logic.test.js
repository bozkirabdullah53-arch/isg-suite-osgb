import {describe, expect, it} from 'vitest';
import {
  approvalMethodLabel,
  formatFileSize,
  normalizePresentationReadiness,
  normalizePresentationVersions,
  parseSavedTrainingId,
  presentationActionState,
  presentationStatusLabel,
  shouldRenderPresentationPanel,
} from './training_presentation_readiness_logic';

function activeReadiness(overrides = {}) {
  return normalizePresentationReadiness({
    training_id: 101,
    company_id: 35,
    enabled: true,
    visible: true,
    manifest_preview_supported: true,
    generation_supported: true,
    generation_allowed: true,
    rollout: {
      global_enabled: true,
      force_off: false,
      allowlist_configured: true,
      pilot_company: true,
      active: true,
    },
    blockers: [],
    checks: [{code: 'presentation_renderer', label: 'Renderer', ok: true, detail: 'Hazır'}],
    ...overrides,
  });
}

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
      generation_allowed: false,
      rollout: {global_enabled: false, active: false},
      read_only: true,
      core_training_unaffected: true,
    });
    expect(view.trainingId).toBe(101);
    expect(view.readOnly).toBe(true);
    expect(view.coreTrainingUnaffected).toBe(true);
    expect(shouldRenderPresentationPanel(view)).toBe(false);
    expect(view.generationAllowed).toBe(false);
  });

  it('hides the panel for a non-pilot company even when global flag is enabled', () => {
    const view = normalizePresentationReadiness({
      training_id: 101,
      enabled: false,
      visible: false,
      generation_allowed: false,
      rollout: {
        global_enabled: true,
        force_off: false,
        allowlist_configured: true,
        pilot_company: false,
        active: false,
      },
    });
    expect(view.rollout.globalEnabled).toBe(true);
    expect(view.rollout.pilotCompany).toBe(false);
    expect(shouldRenderPresentationPanel(view)).toBe(false);
  });

  it('shows an allowed pilot with verified NACE and no blockers', () => {
    const view = activeReadiness({
      classification: {
        status: 'verified',
        nace_code: '62.01.01',
        nace_description: 'Bilgisayar programlama faaliyetleri',
        hazard_class: 'Az Tehlikeli',
      },
      checks: [
        {code: 'verified_nace_snapshot', label: 'Doğrulanmış NACE snapshot', ok: true, detail: 'Hazır'},
        {code: 'template_contract', label: 'Uzman onaylı sunum şablonu', ok: true, detail: 'Hazır'},
        {code: 'presentation_renderer', label: 'PPTX/PDF üretim servisi', ok: true, detail: 'Hazır'},
      ],
    });

    expect(shouldRenderPresentationPanel(view)).toBe(true);
    expect(view.classification.naceCode).toBe('62.01.01');
    expect(view.blockerCount).toBe(0);
    expect(view.generationSupported).toBe(true);
    expect(view.generationAllowed).toBe(true);
  });

  it('does not hide verified-NACE or topic blockers', () => {
    const view = activeReadiness({
      generation_allowed: false,
      checks: [{code: 'verified_nace_snapshot', label: 'NACE', ok: false, detail: 'Eksik'}],
      blockers: [{code: 'verified_nace_snapshot', detail: 'Eksik'}],
    });
    expect(view.blockerCount).toBe(1);
    expect(view.blockers[0].code).toBe('verified_nace_snapshot');
    expect(view.generationAllowed).toBe(false);
  });
});

describe('NACE presentation version actions', () => {
  const readiness = activeReadiness();

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

  it('allows approval after generation and preserves downloads', () => {
    const versions = normalizePresentationVersions({
      training_id: 101,
      rows: [{
        id: 9,
        training_id: 101,
        version: 3,
        status: 'generated',
        manifest_hash: 'a'.repeat(64),
        outputs: {
          pptx: {storage_key: 'a.pptx', file_hash: 'b'.repeat(64), file_size: 1048576},
          pdf: {storage_key: 'a.pdf', file_hash: 'c'.repeat(64), file_size: 2048},
        },
      }],
    });
    const actions = presentationActionState(readiness, versions);
    expect(actions.canApprove).toBe(true);
    expect(actions.canArchive).toBe(false);
    expect(actions.canDownloadPptx).toBe(true);
    expect(actions.canDownloadPdf).toBe(true);
    expect(formatFileSize(1048576)).toBe('1.0 MB');
    expect(formatFileSize(2048)).toBe('2 KB');
  });

  it('normalizes immutable approval and allows archive only after approval', () => {
    const versions = normalizePresentationVersions({
      training_id: 101,
      rows: [{
        id: 10,
        training_id: 101,
        version: 4,
        status: 'approved',
        manifest_hash: 'a'.repeat(64),
        outputs: {
          pptx: {storage_key: 'a.pptx', file_hash: 'b'.repeat(64)},
          pdf: {storage_key: 'a.pdf', file_hash: 'c'.repeat(64)},
        },
        approval: {
          id: 77,
          approval_method: 'application_approval',
          approver: {name: 'A Uzmanı', role: 'safety_specialist'},
          hashes: {manifest: 'a'.repeat(64), pptx: 'b'.repeat(64), pdf: 'c'.repeat(64)},
          legal_notice: 'Nitelikli elektronik imza değildir.',
          event_hash: 'd'.repeat(64),
          immutable: true,
        },
      }],
    });
    expect(versions.latest.approval.approverName).toBe('A Uzmanı');
    expect(versions.latest.approval.immutable).toBe(true);
    const actions = presentationActionState(readiness, versions);
    expect(actions.canApprove).toBe(false);
    expect(actions.canArchive).toBe(true);
    expect(actions.showApproval).toBe(true);
    expect(approvalMethodLabel('application_approval')).toBe('Uygulama içi uzman onayı');
    expect(approvalMethodLabel('qualified_esign')).toBe('Doğrulanmış PAdES e-imza');
  });

  it('disables all write actions when rollout becomes inactive', () => {
    const off = activeReadiness({
      enabled: false,
      visible: false,
      generation_allowed: false,
      rollout: {global_enabled: true, force_off: true, pilot_company: true, active: false},
    });
    const versions = normalizePresentationVersions({training_id: 101, rows: []});
    const actions = presentationActionState(off, versions);
    expect(actions.canPreview).toBe(false);
    expect(actions.canCreateFirst).toBe(false);
    expect(actions.canRender).toBe(false);
    expect(actions.canApprove).toBe(false);
  });

  it('uses clear Turkish status labels', () => {
    expect(presentationStatusLabel('draft')).toBe('Taslak');
    expect(presentationStatusLabel('generated')).toBe('Dosyalar hazır');
    expect(presentationStatusLabel('approved')).toBe('Onaylandı');
    expect(presentationStatusLabel('archived')).toBe('Arşivlendi');
    expect(presentationStatusLabel('failed')).toBe('Üretim hatası');
    expect(presentationStatusLabel('unknown')).toBe('Kayıt yok');
  });
});
