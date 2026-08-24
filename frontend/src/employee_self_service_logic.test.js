import {describe, expect, it} from 'vitest';

import {
  completedSelfServiceTraining,
  formatSelfServiceDate,
  normalizeSelfServicePayload,
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
  });
});
