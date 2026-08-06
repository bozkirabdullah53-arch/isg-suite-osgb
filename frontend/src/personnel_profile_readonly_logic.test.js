import {describe, expect, it} from 'vitest';

import {
  employmentStatusLabel,
  formatProfileDate,
  normalizeEmployeeRows,
  normalizePersonnelProfileSummary,
  normalizePersonnelReadiness,
  normalizeProfessionalRows,
  professionalTypeLabel,
  shouldRenderPersonnelProfileEntry,
} from './personnel_profile_readonly_logic';


describe('personnel profile readiness', () => {
  it('is fail closed unless every rollout gate is active', () => {
    const ready = {
      company_id: 35,
      enabled: true,
      visible: true,
      read_only: true,
      rollout: {
        active: true,
        force_off: false,
        pilot_company: true,
      },
      capabilities: {employee_summary: true},
    };
    expect(normalizePersonnelReadiness(ready).companyId).toBe(35);
    expect(shouldRenderPersonnelProfileEntry(ready)).toBe(true);
    expect(shouldRenderPersonnelProfileEntry({...ready, visible: false})).toBe(false);
    expect(shouldRenderPersonnelProfileEntry({...ready, rollout: {...ready.rollout, force_off: true}})).toBe(false);
    expect(shouldRenderPersonnelProfileEntry({...ready, rollout: {...ready.rollout, pilot_company: false}})).toBe(false);
  });
});


describe('personnel row normalization', () => {
  it('keeps only valid employee rows', () => {
    expect(normalizeEmployeeRows([
      {id: 1, full_name: 'Ayşe Yılmaz', job_title: 'Kaynakçı', is_active: true},
      {id: 0, full_name: 'Geçersiz'},
      {id: 2, full_name: ''},
    ])).toEqual([
      {
        id: 1,
        fullName: 'Ayşe Yılmaz',
        jobTitle: 'Kaynakçı',
        department: '',
        active: true,
      },
    ]);
  });

  it('includes only professionals actively assigned to pilot companies', () => {
    const rows = normalizeProfessionalRows(
      [
        {id: 7, full_name: 'Mehmet Uzman', professional_type: 'safety_specialist', certificate_class: 'A'},
        {id: 8, full_name: 'Hekim Örnek', professional_type: 'workplace_physician'},
      ],
      [
        {professional_id: 7, company_id: 35, status: 'active'},
        {professional_id: 7, company_id: 99, status: 'ended'},
        {professional_id: 8, company_id: 36, status: 'active'},
      ],
      new Set([35]),
    );
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      id: 7,
      companyId: 35,
      companyIds: [35],
      professionalTypeLabel: 'İş Güvenliği Uzmanı',
    });
  });
});


describe('personnel summary normalization', () => {
  it('normalizes an employee summary and detects no restricted data', () => {
    const summary = normalizePersonnelProfileSummary({
      summary_version: 'v1',
      subject: {type: 'employee', id: 41},
      scope: {company_id: 35, company_name: 'Test İşyerim', branch_name: 'Merkez'},
      profile: {
        full_name: 'Ayşe Yılmaz',
        national_identity_masked: '123******90',
        job_title: 'Kaynakçı',
        department: 'Üretim',
        employment_start_date: '2024-01-15',
        employment_status: 'active',
      },
      privacy: {
        data_minimized: true,
        national_identity_full_included: false,
        special_status_included: false,
        health_data_included: false,
        criminal_record_included: false,
        restricted_documents_included: false,
      },
    });
    expect(summary.fullName).toBe('Ayşe Yılmaz');
    expect(summary.nationalIdentityMasked).toBe('123******90');
    expect(summary.restrictedDataIncluded).toBe(false);
    expect(summary.dataMinimized).toBe(true);
  });

  it('marks any restricted-data signal as unsafe', () => {
    expect(normalizePersonnelProfileSummary({
      subject: {type: 'employee', id: 1},
      privacy: {health_data_included: true},
    }).restrictedDataIncluded).toBe(true);
  });
});


describe('labels', () => {
  it('returns Turkish professional and employment labels', () => {
    expect(professionalTypeLabel('workplace_physician')).toBe('İşyeri Hekimi');
    expect(employmentStatusLabel('suspended')).toBe('Askıda');
    expect(formatProfileDate('2024-01-15')).toContain('2024');
  });
});
