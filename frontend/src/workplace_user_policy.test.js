import {describe, expect, it} from 'vitest';

import {
  isWorkplaceKioskUser,
  isWorkplaceAccountUser,
  isWorkplaceManagerUser,
  workplaceModulesForUser,
  workplaceMenuSection,
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
      'workplace_home',
      'workplace_status',
      'employer_oversight',
      'employees',
      'ppe',
      'sds',
      'periyodik_kontrol',
      'ortam_olcum',
      'near_miss',
      'accident',
      'capa',
      'isg_kurulu',
      'personnel_training_records',
      'remote_training',
      'documents',
      'eyas_inbox',
      'health',
      'workplace_backups',
      'site_qr_kiosk',
    ]);
    expect(WORKPLACE_MANAGER_MODULES).not.toContain('companies');
    expect(WORKPLACE_MANAGER_MODULES).not.toContain('users');
    expect(WORKPLACE_MANAGER_MODULES).not.toContain('contracts');
    expect(WORKPLACE_MANAGER_MODULES).not.toContain('finance');
    expect(WORKPLACE_MANAGER_MODULES).not.toContain('training');
    expect(WORKPLACE_MANAGER_MODULES).not.toContain('security');
    expect(WORKPLACE_MANAGER_MODULES[0]).toBe('workplace_home');
    expect(workplaceMenuSection(manager, 'ppe')).toBe('İSG Kayıtları');
    expect(workplaceMenuSection(manager, 'employees')).toBe('Personel ve Eğitim');
    expect(workplaceMenuSection(manager, 'remote_training')).toBe('Personel ve Eğitim');
    expect(workplaceMenuSection(manager, 'workplace_home')).toBe('İşyeri Özeti');
    expect(workplaceMenuSection(manager, 'workplace_status')).toBe('İşyeri Özeti');
    expect(workplaceMenuSection({...manager, company_id: null}, 'ppe')).toBe('');
  });

  it('opens the requested operations for the existing workplace QR password', () => {
    const kiosk = {...manager, email: 'isyeri.42@kiosk.isgsuite.tr'};
    expect(isWorkplaceAccountUser(kiosk)).toBe(true);
    const modules = workplaceModulesForUser(kiosk);
    for (const id of ['employees', 'ppe', 'sds', 'periyodik_kontrol', 'ortam_olcum', 'near_miss', 'accident', 'capa', 'isg_kurulu', 'site_qr_kiosk']) {
      expect(modules).toContain(id);
      expect(workplaceMenuSection(kiosk, id)).not.toBe('');
    }
    expect(modules[0]).toBe('workplace_home');
    for (const id of ['companies', 'users', 'finance', 'contracts', 'health', 'documents', 'training']) {
      expect(modules).not.toContain(id);
    }
    expect(modules).not.toContain('remote_training');
    expect(modules).not.toContain('workplace_status');
    expect(modules).toContain('workplace_backups');
    expect(workplaceModulesForUser({...manager, company_id: null})).toBe(null);
    expect(workplaceModulesForUser({...manager, role: 'safety_specialist'})).toBe(null);
    expect(workplaceModulesForUser({...manager, role: 'read_only'})).toBe(null);
    expect(workplaceModulesForUser(manager)).toEqual(WORKPLACE_MANAGER_MODULES);
  });
});
