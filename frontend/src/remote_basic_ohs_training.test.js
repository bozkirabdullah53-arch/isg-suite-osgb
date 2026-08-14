import {describe, expect, it} from 'vitest';
import {
  employeeAssignmentTimeline,
  formatEmployeeDate,
  sortEmployeeAssignments,
} from './remote_basic_ohs_training.jsx';

const today = new Date(2026, 7, 14, 12, 0, 0);

describe('employee training assignment overview', () => {
  it('keeps future, due-today, overdue, and completed assignments distinguishable', () => {
    expect(employeeAssignmentTimeline({due_date: '2026-08-15'}, today)).toMatchObject({
      key: 'upcoming',
      label: 'Yaklaşan',
    });
    expect(employeeAssignmentTimeline({due_date: '2026-08-14'}, today)).toMatchObject({
      key: 'due',
      label: 'Süresi bugün',
    });
    expect(employeeAssignmentTimeline({due_date: '2026-08-13'}, today)).toMatchObject({
      key: 'overdue',
      label: 'Süresi geçmiş',
    });
    expect(employeeAssignmentTimeline({status: 'completed', due_date: '2026-08-01'}, today)).toMatchObject({
      key: 'completed',
      label: 'Tamamlandı',
    });
  });

  it('orders all assignments without dropping historical records', () => {
    const rows = [
      {id: 1, due_date: '2026-08-20', assigned_at: '2026-08-01T10:00:00Z'},
      {id: 2, due_date: '2026-08-13', assigned_at: '2026-08-02T10:00:00Z'},
      {id: 3, status: 'completed', due_date: '2026-07-01', assigned_at: '2026-08-03T10:00:00Z'},
      {id: 4, due_date: '2026-08-14', assigned_at: '2026-08-04T10:00:00Z'},
    ];

    expect(sortEmployeeAssignments(rows, today).map((row) => row.id)).toEqual([2, 4, 1, 3]);
    expect(sortEmployeeAssignments(rows, today)).toHaveLength(4);
  });

  it('formats assignment dates using Turkish date order', () => {
    expect(formatEmployeeDate('2026-08-14')).toBe('14.08.2026');
    expect(formatEmployeeDate(null)).toBe('Belirlenmedi');
  });
});
