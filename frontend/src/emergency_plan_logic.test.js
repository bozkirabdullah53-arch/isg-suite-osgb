import {describe, expect, it} from 'vitest';

import {
  addYears,
  cloneDetails,
  createEmptyPlan,
  getReadiness,
  reviewYearsForHazard,
} from './emergency_plan_logic';

describe('emergency plan premium helpers', () => {
  it('uses the regulatory review cadence for default plan dates', () => {
    expect(reviewYearsForHazard('cok_tehlikeli')).toBe(2);
    expect(reviewYearsForHazard('tehlikeli')).toBe(4);
    expect(reviewYearsForHazard('az_tehlikeli')).toBe(6);
    expect(addYears('2026-08-30', 2)).toBe('2028-08-30');
  });

  it('keeps a safe default details shape while removing duplicate scenarios', () => {
    const details = cloneDetails({emergency_types: ['yangin', 'yangin'], external_contacts: []});
    expect(details.emergency_types).toEqual(['yangin']);
    expect(details.visitors_included).toBe(true);
    expect(details.external_contacts).toEqual([]);
  });

  it('falls back to a transparent basic readiness result for old API payloads', () => {
    const result = getReadiness({plan_date: '2026-01-01', next_review_date: '2030-01-01', has_scene: false});
    expect(result.pct).toBe(33);
    expect(result.status).toBe('action');
    expect(result.missing).toContain('Kat krokisi ve işaretler');
  });

  it('creates a dated plan draft without hiding required later checks', () => {
    const draft = createEmptyPlan({companyId: 4, hazardClass: 'cok_tehlikeli', today: '2026-08-30'});
    expect(draft.company_id).toBe(4);
    expect(draft.plan_date).toBe('2026-08-30');
    expect(draft.next_review_date).toBe('2028-08-30');
    expect(draft.details.emergency_types).toEqual([]);
  });
});
