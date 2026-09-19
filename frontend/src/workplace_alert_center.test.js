import {describe, expect, it} from 'vitest';
import {
  workplaceAlertDeadlines,
  workplaceDateText,
  workplaceDeadlineText,
  workplaceStatusTone,
} from './workplace_alert_center';

describe('workplace alert center', () => {
  it('puts overdue records before upcoming records and keeps the preview bounded', () => {
    const deadlines = workplaceAlertDeadlines({
      deadlines: [
        {title: '90 gün', status: 'scheduled', days_left: 90},
        {title: 'yaklaşan', status: 'due_soon', days_left: 5},
        {title: 'geciken', status: 'overdue', days_left: -2},
        {title: 'uzak', status: 'scheduled', days_left: 120},
      ],
    }, {limit: 3});

    expect(deadlines.map((row) => row.title)).toEqual(['geciken', 'yaklaşan', '90 gün']);
  });

  it('formats day labels without hiding today', () => {
    expect(workplaceDeadlineText({days_left: -4})).toBe('4 gün gecikti');
    expect(workplaceDeadlineText({days_left: 0})).toBe('Bugün');
    expect(workplaceDeadlineText({days_left: 12})).toBe('12 gün kaldı');
  });

  it('shows ISO due dates in Turkish day-month-year order', () => {
    expect(workplaceDateText('2026-09-18')).toBe('18.09.2026');
    expect(workplaceDateText(null)).toBe('—');
  });

  it('falls back to a compliant visual tone', () => {
    expect(workplaceStatusTone('critical')).toBe('critical');
    expect(workplaceStatusTone('warning')).toBe('warning');
    expect(workplaceStatusTone('unknown')).toBe('compliant');
  });
});
