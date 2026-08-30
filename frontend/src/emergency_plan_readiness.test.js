import {describe, expect, it} from 'vitest';
import {buildEmergencyPlanReadiness} from './emergency_plan_readiness';

const completePlan = {
  plan_date: '2026-01-10',
  next_review_date: '2027-01-10',
  assembly_areas: 'Açık otopark',
  scenario_summary: 'Yangın ve deprem tahliye sırası',
  has_scene: true,
  review_status: 'ok',
};

const completeInsight = {
  checks: {exit: 2},
  team_readiness: {ready: true},
  drill_readiness: {status: 'current', latest_date: '2026-02-01'},
};

describe('emergency plan readiness', () => {
  it('marks a complete digital evidence set as ready', () => {
    const result = buildEmergencyPlanReadiness(completePlan, completeInsight);

    expect(result.percent).toBe(100);
    expect(result.attention).toBe(false);
    expect(result.checks.every((item) => item.ok)).toBe(true);
  });

  it('keeps a plan in attention when team or drill evidence is missing', () => {
    const result = buildEmergencyPlanReadiness(completePlan, {
      ...completeInsight,
      team_readiness: {ready: false},
      drill_readiness: {status: 'missing'},
    });

    expect(result.percent).toBe(75);
    expect(result.attention).toBe(true);
    expect(result.checks.filter((item) => !item.ok).map((item) => item.label)).toEqual([
      'Acil ekip kadrosu',
      'Tamamlanmış tatbikat',
    ]);
  });
});
