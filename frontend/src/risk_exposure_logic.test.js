import {describe, expect, it} from 'vitest';
import {canViewExposurePeople, exposureTrainingCsv, matchedWorkerCount, validSelectedIds, visibleExposurePeople} from './risk_exposure_logic';

const data = {
  company: {id: 1, name: 'Firma'}, scope: {label: 'Kimyasal'},
  employees: [
    {id: 1, full_name: 'Aynı İsim', department: 'Şarj', matches: [{risk_id: 10, reasons: ['Bölüm: Şarj']}]},
    {id: 2, full_name: 'Aynı İsim', department: 'Depo', matches: [{risk_id: 11, reasons: ['Görev: Depo']}]},
    {id: 3, full_name: '=HYPERLINK("x")', department: 'Bakım', matches: []},
  ],
  risks: [{id: 10, hazard: 'Asit', risk_code: 'R-10', risk_definition: 'Sıçrama'}, {id: 11, hazard: 'Solvent', risk_code: 'R-11'}],
};

describe('risk people and training selection', () => {
  it('keeps the role and workplace boundary narrow', () => {
    expect(canViewExposurePeople({role: 'company_admin'})).toBe(false);
    expect(canViewExposurePeople({role: 'company_admin', company_id: 1})).toBe(true);
    expect(canViewExposurePeople({role: 'safety_specialist'})).toBe(true);
    expect(canViewExposurePeople({role: 'workplace_physician'})).toBe(true);
    expect(canViewExposurePeople({role: 'other_health_personnel'})).toBe(false);
    expect(canViewExposurePeople({role: 'read_only'})).toBe(false);
  });
  it('shows actual identity matches when the reported estimate differs', () => {
    expect(matchedWorkerCount({matched_worker_count: 0, exposed_worker_count: 25})).toBe(0);
    expect(matchedWorkerCount({exposed_worker_count: 3})).toBe(0);
  });
  it('preserves distinct people with identical names and filters one risk', () => {
    expect(visibleExposurePeople(data)).toHaveLength(2);
    expect(visibleExposurePeople(data, {riskId: 10}).map((p) => p.id)).toEqual([1]);
    expect(visibleExposurePeople(data, {query: 'şarj'}).map((p) => p.id)).toEqual([1]);
  });
  it('includes unmatched active workers only through explicit manual selection', () => {
    expect(visibleExposurePeople(data, {includeUnmatched: true})).toHaveLength(3);
    expect(validSelectedIds(data, [1, '1', 3, 999])).toEqual([1, 3]);
  });
  it('exports only selected identities, marks manual selection and escapes formulas', () => {
    const csv = exposureTrainingCsv(data, [1, 3, 999], 10);
    expect(csv).toContain('Bölüm: Şarj');
    expect(csv).not.toContain('Görev: Depo');
    expect(csv).toContain('Manuel eğitim seçimi');
    expect(csv).toContain('doğrulanmış maruziyet kaydı değildir');
    expect(csv).toContain("'=HYPERLINK");
    expect(csv.split('\r\n')).toHaveLength(3);
  });
});
