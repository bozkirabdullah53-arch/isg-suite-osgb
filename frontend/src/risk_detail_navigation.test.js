import {describe, expect, it} from 'vitest';
import {isMatchingRiskId, normalizeRiskId} from './risk_detail_navigation';

describe('risk detail navigation identity', () => {
  it('normalizes only positive integer risk ids', () => {
    expect(normalizeRiskId('23')).toBe(23);
    expect(normalizeRiskId(23)).toBe(23);
    expect(normalizeRiskId('00023')).toBe(23);
    expect(normalizeRiskId('')).toBeNull();
    expect(normalizeRiskId('23.5')).toBeNull();
    expect(normalizeRiskId(0)).toBeNull();
    expect(normalizeRiskId(-1)).toBeNull();
  });

  it('accepts a response only when it belongs to the requested risk', () => {
    expect(isMatchingRiskId(23, '23')).toBe(true);
    expect(isMatchingRiskId('023', 23)).toBe(true);
    expect(isMatchingRiskId(24, 23)).toBe(false);
    expect(isMatchingRiskId(null, 23)).toBe(false);
  });
});
