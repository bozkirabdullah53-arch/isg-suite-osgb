import {describe, expect, it} from 'vitest';
import {
  canUseVisitCheckInOutQr,
  canUseVisitCheckInOutQrForCompany,
  isVisitQrEnabledForCompany,
} from './visit_qr_policy';

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

  it('follows the per-workplace OSGB policy without changing the role rule', () => {
    const user = {role: 'safety_specialist'};
    expect(isVisitQrEnabledForCompany({visit_qr_enabled: true})).toBe(true);
    expect(isVisitQrEnabledForCompany({visit_qr_enabled: false})).toBe(false);
    expect(canUseVisitCheckInOutQrForCompany(user, {visit_qr_enabled: true})).toBe(true);
    expect(canUseVisitCheckInOutQrForCompany(user, {visit_qr_enabled: false})).toBe(false);
    // Old API payloads without the new field remain enabled.
    expect(canUseVisitCheckInOutQrForCompany(user, {})).toBe(true);
  });
});
