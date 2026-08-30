import {describe, expect, it} from 'vitest';
import {
  PROFESSIONAL_MENU_MODULES,
  professionalHomeModule,
  professionalMenuSection,
  professionalModulesForUser,
} from './professional_navigation';

describe('professional navigation', () => {
  it('puts the home page first for the requested field roles', () => {
    expect(PROFESSIONAL_MENU_MODULES.safety_specialist[0]).toBe('dashboard');
    expect(PROFESSIONAL_MENU_MODULES.workplace_physician[0]).toBe('dashboard');
    expect(professionalHomeModule('safety_specialist', PROFESSIONAL_MENU_MODULES.safety_specialist)).toBe('dashboard');
    expect(professionalHomeModule('workplace_physician', PROFESSIONAL_MENU_MODULES.workplace_physician)).toBe('dashboard');
  });

  it('keeps notebook upload and QR scan as separate actions', () => {
    for (const role of ['safety_specialist', 'workplace_physician']) {
      const modules = PROFESSIONAL_MENU_MODULES[role];
      expect(modules).toContain('visit_notebook');
      expect(modules).toContain('visit_qr');
      expect(modules.indexOf('visit_notebook')).not.toBe(modules.indexOf('visit_qr'));
    }
    expect(professionalMenuSection('safety_specialist', 'visit_notebook')).toBe('Günlük İş Akışı');
    expect(professionalMenuSection('workplace_physician', 'visit_qr')).toBe('Günlük İş Akışı');
  });

  it('does not expose QR scan to an individual specialist', () => {
    for (const role of ['safety_specialist', 'workplace_physician']) {
      const modules = professionalModulesForUser(role, {isIndividual: true});
      expect(modules).not.toContain('visit_qr');
      expect(modules).not.toContain('belge_onay');
      expect(modules).not.toContain('eyas_inbox');
      expect(modules).toContain('visit_notebook');
    }
    expect(professionalModulesForUser('safety_specialist', {isIndividual: true})).not.toContain('customer_portal');
  });
});
