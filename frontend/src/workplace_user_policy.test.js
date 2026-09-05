import {describe, expect, it} from 'vitest';

import {
  isWorkplaceKioskUser,
  isWorkplaceManagerUser,
  isWorkplaceModuleReadOnly,
  WORKPLACE_MANAGER_EDITABLE_MODULES,
  WORKPLACE_MANAGER_MODULES,
  WORKPLACE_MANAGER_READONLY_MODULES,
} from './workplace_user_policy';

describe('workplace user policy', () => {
  const manager = {
    role: 'company_admin',
    company_id: 42,
    osgb_id: 7,
    email: 'ik.yetkilisi@example.com',
  };

  it('treats the existing QR workplace account as the same workplace account', () => {
    expect(isWorkplaceManagerUser(manager)).toBe(true);
    expect(isWorkplaceManagerUser({...manager, company_id: null})).toBe(false);
    expect(isWorkplaceManagerUser({...manager, role: 'safety_specialist'})).toBe(false);

    const kiosk = {...manager, email: 'isyeri.42@kiosk.isgsuite.tr'};
    expect(isWorkplaceManagerUser(kiosk)).toBe(true);
    expect(isWorkplaceKioskUser(kiosk)).toBe(false);
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

  it('locks the four requested workplace modules to view-only', () => {
    expect(WORKPLACE_MANAGER_READONLY_MODULES).toEqual([
      'employer_oversight',
      'personnel_training_records',
      'documents',
      'health',
    ]);
    expect(WORKPLACE_MANAGER_EDITABLE_MODULES).toEqual([
      'employees',
      'ppe',
      'sds',
      'periyodik_kontrol',
      'eyas_inbox',
      'ortam_olcum',
      'accident',
      'near_miss',
    ]);
    for (const moduleId of WORKPLACE_MANAGER_READONLY_MODULES) {
      expect(isWorkplaceModuleReadOnly(manager, moduleId)).toBe(true);
    }
    for (const moduleId of WORKPLACE_MANAGER_EDITABLE_MODULES) {
      expect(isWorkplaceModuleReadOnly(manager, moduleId)).toBe(false);
    }
  });
});
