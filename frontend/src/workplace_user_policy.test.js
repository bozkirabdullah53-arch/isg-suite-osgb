import {describe, expect, it} from 'vitest';

import {
  isWorkplaceKioskUser,
  isWorkplaceManagerUser,
  WORKPLACE_MANAGER_MODULES,
} from './workplace_user_policy';

describe('workplace user policy', () => {
  const manager = {
    role: 'company_admin',
    company_id: 42,
    osgb_id: 7,
    email: 'ik.yetkilisi@example.com',
  };

  it('separates a workplace manager from the OSGB administrator and QR kiosk', () => {
    expect(isWorkplaceManagerUser(manager)).toBe(true);
    expect(isWorkplaceManagerUser({...manager, company_id: null})).toBe(false);
    expect(isWorkplaceManagerUser({...manager, role: 'safety_specialist'})).toBe(false);
    expect(isWorkplaceManagerUser({...manager, email: 'isyeri.42@kiosk.isgsuite.tr'})).toBe(false);
    expect(isWorkplaceKioskUser({...manager, email: 'isyeri.42@kiosk.isgsuite.tr'})).toBe(true);
  });

  it('exposes the approved workplace operational modules in the intended order', () => {
    expect(WORKPLACE_MANAGER_MODULES).toEqual([
      'employer_oversight',
      'employees',
      'ppe',
      'sds',
      'periyodik_kontrol',
      'personnel_training_records',
      'documents',
      'eyas_inbox',
      'ortam_olcum',
      'accident',
      'near_miss',
      'health',
      'site_qr_kiosk',
    ]);
    expect(WORKPLACE_MANAGER_MODULES).not.toContain('companies');
    expect(WORKPLACE_MANAGER_MODULES).not.toContain('users');
    expect(WORKPLACE_MANAGER_MODULES).not.toContain('contracts');
    expect(WORKPLACE_MANAGER_MODULES).not.toContain('finance');
    expect(WORKPLACE_MANAGER_MODULES).not.toContain('training');
    expect(WORKPLACE_MANAGER_MODULES).not.toContain('security');
  });
});
