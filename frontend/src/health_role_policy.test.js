import {describe, expect, it} from 'vitest';
import {
  employerHealthDetails,
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

  it('opens only the masked read-only view to the workplace account', () => {
    const manager = {
      role: 'company_admin',
      company_id: 42,
      email: 'ik.yetkilisi@example.com',
    };
    expect(canViewHealthRecords(manager)).toBe(true);
    expect(canEditHealthRecords(manager)).toBe(false);
    expect(canViewEmployerFitness(manager)).toBe(true);

    expect(canViewHealthRecords({...manager, company_id: null})).toBe(false);
    expect(canViewHealthRecords({...manager, email: 'isyeri.42@kiosk.isgsuite.tr'})).toBe(true);
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


describe('employer clinical confidentiality', () => {
  it('keeps fitness restrictions but excludes notes, report names and future clinical fields', () => {
    const details = employerHealthDetails([
      ['Personel', 'Ayşe Örnek'], ['Uygunluk', 'Kısıtlı'],
      ['Kısıtlamalar', 'Gece vardiyasında çalışamaz'],
      ['Özet', 'Gizli hekim notu'], ['Rapor dosyası', 'Klinik rapor.pdf'],
      ['Yeni klinik alan', 'Gizli laboratuvar sonucu'],
    ]);
    expect(details).toHaveLength(3);
    expect(details.flat().join(' ')).toContain('Gece vardiyasında çalışamaz');
    expect(details.flat().join(' ')).not.toMatch(/Gizli|Klinik rapor/);
  });
});
