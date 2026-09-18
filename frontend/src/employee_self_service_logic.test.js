import {describe, expect, it} from 'vitest';

import {
  certificateKindLabel,
  completedSelfServiceTraining,
  filterSelfServiceCertificates,
  formatSelfServiceDate,
  isEmployeeNotificationVisible,
  normalizeSelfServicePayload,
  selfServiceCertificateFilename,
  selfServiceFeatureEnabled,
  totalSelfServiceTraining,
} from './employee_self_service_logic';


describe('employee self-service rollout', () => {
  it('feature flag is opt-in and exact', () => {
    expect(selfServiceFeatureEnabled('true')).toBe(true);
    expect(selfServiceFeatureEnabled('TRUE')).toBe(true);
    expect(selfServiceFeatureEnabled('1')).toBe(false);
    expect(selfServiceFeatureEnabled(undefined)).toBe(false);
  });
});


describe('employee self-service payload', () => {
  it('keeps the mobile summary scoped and counts both training streams', () => {
    const summary = normalizeSelfServicePayload({
      scope: {company_name: 'Test İşyeri', branch_name: 'Merkez'},
      employee: {full_name: 'Ayşe Yılmaz', job_title: 'Kaynakçı'},
      training: {
        classroom: {total: 2, completed: 1, history: [{id: 1}]},
        remote: {available: true, total: 1, completed: 1, assignments: [{id: 3}]},
      },
      certificates: {
        total: 2,
        downloadable: 1,
        items: [{id: 'classroom-1', kind: 'classroom', downloadable: true}],
      },
      ppe: {total: 1, items: [{id: 7}]},
      notifications: {unread: 2, items: []},
      health: {
        has_record: true,
        next_examination_date: '2027-01-10',
        details_included: false,
      },
    });

    expect(summary.scope.companyName).toBe('Test İşyeri');
    expect(summary.employee.fullName).toBe('Ayşe Yılmaz');
    expect(totalSelfServiceTraining(summary)).toBe(3);
    expect(completedSelfServiceTraining(summary)).toBe(2);
    expect(summary.health.detailsIncluded).toBe(false);
    expect(formatSelfServiceDate(summary.health.nextExaminationDate)).toContain('2027');
    expect(summary.certificates.downloadable).toBe(1);
    expect(summary.certificates.items).toHaveLength(1);
  });

  it('names the employee certificate download from the stored number', () => {
    expect(certificateKindLabel('remote')).toBe('Uzaktan eğitim');
    expect(selfServiceCertificateFilename({
      certificate_number: 'EGT-000001-000002',
      kind: 'classroom',
      source_id: 9,
    })).toBe('egitim-katilim-belgesi-EGT-000001-000002.pdf');
  });

  it('searches all documents with Turkish text and filters readiness', () => {
    const documents = [
      {title: 'İLK YARDIM', kind: 'classroom', certificate_number: 'EGT-42', downloadable: true},
      {title: 'Hijyen Eğitimi', kind: 'remote', downloadable: false},
    ];
    expect(filterSelfServiceCertificates(documents, 'ilk yardım')).toEqual([documents[0]]);
    expect(filterSelfServiceCertificates(documents, 'egt-42', 'ready')).toEqual([documents[0]]);
    expect(filterSelfServiceCertificates(documents, 'uzaktan', 'pending')).toEqual([documents[1]]);
    expect(filterSelfServiceCertificates(documents, 'ilk', 'pending')).toEqual([]);
    expect(filterSelfServiceCertificates(documents)).toHaveLength(2);
  });

  it('hides annual-plan management notifications from the employee view', () => {
    expect(isEmployeeNotificationVisible({entity_type: 'annual_plan', title: 'Geciken yıllık plan faaliyeti'})).toBe(false);
    expect(isEmployeeNotificationVisible({entity_type: 'remote_training', title: 'Eğitiminiz devam ediyor'})).toBe(true);
  });
});
