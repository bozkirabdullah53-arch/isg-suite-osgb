import {describe, expect, it} from 'vitest';
import {annualPlanStatusWithCompletion} from './annual_plan_status';

describe('annual plan completion status', () => {
  it('keeps a plan completed when a completion date is entered', () => {
    expect(annualPlanStatusWithCompletion('delayed', '2026-09-22')).toBe('completed');
  });

  it('preserves the selected status when no completion date exists', () => {
    expect(annualPlanStatusWithCompletion('planned', '')).toBe('planned');
  });
});
