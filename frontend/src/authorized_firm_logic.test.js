import {describe, expect, it} from 'vitest';

import {
  buildAuthorizedFirmQuery,
  normalizeProfilePayload,
  readinessTone,
  toggleCompletedStep,
  validateDateRange,
  validityTone,
} from './authorized_firm_logic.js';

describe('authorized firm UI logic', () => {
  it('maps 30/60/90 day validity states without hiding severity', () => {
    expect(validityTone('valid')).toBe('good');
    expect(validityTone('due_90')).toBe('info');
    expect(validityTone('due_60')).toBe('warn');
    expect(validityTone('due_30')).toBe('warn');
    expect(validityTone('expired')).toBe('danger');
    expect(readinessTone('critical')).toBe('danger');
  });

  it('encodes only active filters', () => {
    expect(buildAuthorizedFirmQuery({q: 'Ankara & Çankaya', active: true, province: ''}))
      .toBe('?q=Ankara+%26+%C3%87ankaya&active=true');
  });

  it('normalizes identifiers and empty optional fields', () => {
    expect(normalizeProfilePayload({osgb_id: '4', company_id: '8', notes: '', firm_name: 'Firma'}))
      .toEqual({osgb_id: 4, company_id: 8, notes: null, firm_name: 'Firma'});
  });

  it('rejects reversed date ranges', () => {
    expect(validateDateRange('2026-08-30', '2026-08-20', 'Yetki')).toContain('önce');
    expect(validateDateRange('2026-08-20', '2026-08-30', 'Yetki')).toBe('');
  });

  it('keeps onboarding steps unique and ordered', () => {
    expect(toggleCompletedStep([3, 1, 3], 2)).toEqual([1, 2, 3]);
    expect(toggleCompletedStep([1, 2, 3], 2)).toEqual([1, 3]);
  });
});
