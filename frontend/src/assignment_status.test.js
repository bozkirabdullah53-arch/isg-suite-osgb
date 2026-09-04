import {describe, expect, it} from 'vitest';
import {effectiveAssignmentStatus} from './assignment_status';

describe('effectiveAssignmentStatus', () => {
  const today = '2026-09-04';

  it('marks a future active assignment as planned', () => {
    expect(effectiveAssignmentStatus({status: 'active', start_date: '2026-09-07'}, today)).toBe('planned');
  });

  it('keeps assignments effective today active', () => {
    expect(effectiveAssignmentStatus({status: 'active', start_date: today}, today)).toBe('active');
    expect(effectiveAssignmentStatus({status: 'active', start_date: '2026-08-01', end_date: today}, today)).toBe('active');
  });

  it('marks an ended active assignment as expired', () => {
    expect(effectiveAssignmentStatus({status: 'active', start_date: '2026-08-01', end_date: '2026-09-03'}, today)).toBe('expired');
  });

  it('preserves explicit suspended and ended states', () => {
    expect(effectiveAssignmentStatus({status: 'suspended', start_date: '2026-09-07'}, today)).toBe('suspended');
    expect(effectiveAssignmentStatus({status: 'ended', start_date: '2026-08-01'}, today)).toBe('ended');
  });
});
