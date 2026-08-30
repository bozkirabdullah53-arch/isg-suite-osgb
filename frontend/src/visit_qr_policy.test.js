import {describe, expect, it} from 'vitest';
import {canUseVisitCheckInOutQr} from './visit_qr_policy';

describe('visit QR check-in/out policy', () => {
  it('disables workplace QR entry and exit for an individual specialist', () => {
    expect(canUseVisitCheckInOutQr({
      role: 'safety_specialist',
      is_individual: true,
    })).toBe(false);
  });

  it('keeps workplace QR entry and exit for OSGB-linked field professionals', () => {
    expect(canUseVisitCheckInOutQr({
      role: 'safety_specialist',
      is_individual: false,
    })).toBe(true);
    expect(canUseVisitCheckInOutQr({
      role: 'workplace_physician',
      is_individual: false,
    })).toBe(true);
    expect(canUseVisitCheckInOutQr({
      role: 'other_health_personnel',
      is_individual: false,
    })).toBe(true);
  });

  it('does not expose field QR actions to administrative roles', () => {
    expect(canUseVisitCheckInOutQr({role: 'company_admin'})).toBe(false);
    expect(canUseVisitCheckInOutQr({role: 'global_admin'})).toBe(false);
  });
});
