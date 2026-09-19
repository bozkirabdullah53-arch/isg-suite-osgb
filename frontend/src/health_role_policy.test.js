import {describe, expect, it} from 'vitest';
import {
  canEditHealthRecords,
  canLoadHealthAnalysis,
  canViewEmployerFitness,
  canViewHealthRecords,
} from './health_role_policy';

describe('health role request policy', () => {
  it('only enables the physician-only analysis request for workplace physicians', () => {
    expect(canLoadHealthAnalysis('workplace_physician')).toBe(true);
    expect(canLoadHealthAnalysis('other_health_personnel')).toBe(false);
    expect(canLoadHealthAnalysis('safety_specialist')).toBe(false);
    expect(canLoadHealthAnalysis('company_admin')).toBe(false);
  });

  it('opens only the masked read-only view to every company-bound workplace login', () => {
    const manager = {
      role: 'company_admin',
      company_id: 42,
      email: 'ik.yetkilisi@example.com',
    };
    expect(canViewHealthRecords(manager)).toBe(true);
    expect(canEditHealthRecords(manager)).toBe(false);
    expect(canViewEmployerFitness(manager)).toBe(true);

    expect(canViewHealthRecords({...manager, company_id: null})).toBe(false);
    const existingWorkplaceLogin = {...manager, email: 'isyeri.42@kiosk.isgsuite.tr'};
    expect(canViewHealthRecords(existingWorkplaceLogin)).toBe(true);
    expect(canEditHealthRecords(existingWorkplaceLogin)).toBe(false);
    expect(canViewEmployerFitness(existingWorkplaceLogin)).toBe(true);
  });

  it('keeps clinical editing and employer-document boundaries unchanged', () => {
    const physician = {role: 'workplace_physician'};
    const dsp = {role: 'other_health_personnel'};
    expect(canEditHealthRecords(physician)).toBe(true);
    expect(canEditHealthRecords(dsp)).toBe(true);
    expect(canViewHealthRecords(physician)).toBe(true);
    expect(canViewHealthRecords(dsp)).toBe(true);
    expect(canViewEmployerFitness(physician)).toBe(true);
    expect(canViewEmployerFitness(dsp)).toBe(false);
  });
});
