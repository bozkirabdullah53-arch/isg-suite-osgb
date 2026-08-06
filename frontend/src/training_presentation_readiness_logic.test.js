import {describe, expect, it} from 'vitest';
import {
  normalizePresentationReadiness,
  parseSavedTrainingId,
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
  });

  it('normalizes verified NACE checks without enabling generation', () => {
    const view = normalizePresentationReadiness({
      training_id: 101,
      enabled: true,
      visible: true,
      read_only: true,
      generation_supported: false,
      generation_allowed: false,
      core_training_unaffected: true,
      classification: {
        status: 'verified',
        nace_code: '62.01.01',
        nace_description: 'Bilgisayar programlama faaliyetleri',
        hazard_class: 'Az Tehlikeli',
      },
      checks: [
        {code: 'verified_nace_snapshot', label: 'Doğrulanmış NACE snapshot', ok: true, detail: 'Hazır'},
        {code: 'template_contract', label: 'Uzman onaylı sunum şablonu', ok: false, detail: 'Bekleniyor'},
      ],
      blockers: [{code: 'template_contract'}],
      warnings: [],
      next_action: 'Şablon onayı bekleniyor.',
    });

    expect(shouldRenderPresentationPanel(view)).toBe(true);
    expect(view.classification.naceCode).toBe('62.01.01');
    expect(view.checks).toHaveLength(2);
    expect(view.blockerCount).toBe(1);
    expect(view.generationSupported).toBe(false);
    expect(view.generationAllowed).toBe(false);
  });
});
