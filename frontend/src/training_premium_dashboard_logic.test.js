import {describe, expect, it} from 'vitest';
import {
  actionTargetLabel,
  dashboardHeadline,
  normalizeTrainingDashboard,
  statusTone,
} from './training_premium_dashboard_logic';

describe('training premium dashboard logic', () => {
  it('normalizes disabled or missing payload safely', () => {
    expect(normalizeTrainingDashboard(null)).toEqual({
      enabled: false,
      companyId: null,
      today: null,
      trackingFrom: null,
      summary: {},
      actions: [],
      rows: [],
      safety: {},
    });
  });

  it('prioritizes red actions before warnings', () => {
    expect(dashboardHeadline({work_start_missing: 2, basic_overdue: 3})).toEqual({
      tone: 'danger',
      label: '5 öncelikli işlem var',
    });
    expect(dashboardHeadline({basic_waiting: 4, result_pending: 1})).toEqual({
      tone: 'warning',
      label: '5 işlem bekliyor',
    });
    expect(dashboardHeadline({basic_ok: 8})).toEqual({
      tone: 'ok',
      label: 'Acil eğitim işlemi görünmüyor',
    });
  });

  it('keeps historical Work Start state neutral', () => {
    expect(statusTone('neutral')).toBe('neutral');
    expect(statusTone('unexpected')).toBe('neutral');
  });

  it('maps action targets to existing Turkish Training tabs', () => {
    expect(actionTargetLabel('temel')).toBe('Temel İSG Eğitimi');
    expect(actionTargetLabel('yenileme')).toBe('Yenileme Takibi');
    expect(actionTargetLabel('kayitlar')).toBe('Kayıtlar');
  });
});
