import {describe, expect, it} from 'vitest';
import {canLoadHealthAnalysis} from './health_role_policy';

describe('health role request policy', () => {
  it('only enables the physician-only analysis request for workplace physicians', () => {
    expect(canLoadHealthAnalysis('workplace_physician')).toBe(true);
    expect(canLoadHealthAnalysis('other_health_personnel')).toBe(false);
    expect(canLoadHealthAnalysis('safety_specialist')).toBe(false);
    expect(canLoadHealthAnalysis('company_admin')).toBe(false);
  });
});
