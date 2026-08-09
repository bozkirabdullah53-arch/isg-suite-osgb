import {describe, expect, it} from 'vitest';
import {
  lifecycleTone,
  normalizePremiumPolicy,
  parseTrainingIdFromText,
  ruleSummary,
  shouldReplacePrematureVerification,
} from './training_premium_lifecycle_logic';

describe('training premium lifecycle logic', () => {
  it('normalizes disabled policy safely', () => {
    expect(normalizePremiumPolicy(null).enabled).toBe(false);
    expect(shouldReplacePrematureVerification(null)).toBe(false);
  });

  it('parses training id from generated certificate number', () => {
    expect(parseTrainingIdFromText('Belge EGT-000090-000123')).toBe(90);
    expect(parseTrainingIdFromText('Kayıt #118')).toBe(118);
  });

  it('summarizes official 2026 hours without English copy', () => {
    const policy = {
      enabled: true,
      rules: {
        initial_basic: {hours: {'Çok Tehlikeli': 16}},
        repeat_basic: {hours: {'Çok Tehlikeli': 8}},
        work_specific: {hours: {'Çok Tehlikeli': 4}},
        lesson_definition: '45 dakika ders + 15 dakika ara dinlenmesi',
      },
    };
    expect(ruleSummary(policy, 'Çok Tehlikeli')).toEqual({
      initialHours: 16,
      repeatHours: 8,
      workSpecificHours: 4,
      lessonDefinition: '45 dakika ders + 15 dakika ara dinlenmesi',
    });
  });

  it('maps lifecycle stages to stable visual tones', () => {
    expect(lifecycleTone('planned')).toBe('info');
    expect(lifecycleTone('results_pending')).toBe('warning');
    expect(lifecycleTone('document_ready')).toBe('ready');
    expect(lifecycleTone('cancelled')).toBe('danger');
  });
});
