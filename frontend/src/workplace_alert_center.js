const STATUS_PRIORITY = Object.freeze({overdue: 0, due_soon: 1, scheduled: 2});

export function workplaceAlertDeadlines(statusCenter, {limit = 6, horizonDays = 90} = {}) {
  const rows = Array.isArray(statusCenter?.deadlines) ? statusCenter.deadlines : [];
  return rows
    .filter((row) => {
      const days = Number(row?.days_left);
      if (!Number.isFinite(days)) return false;
      return days < 0 || days <= horizonDays;
    })
    .sort((left, right) => {
      const statusOrder = (STATUS_PRIORITY[left?.status] ?? 9) - (STATUS_PRIORITY[right?.status] ?? 9);
      if (statusOrder) return statusOrder;
      const daysOrder = Number(left?.days_left) - Number(right?.days_left);
      if (daysOrder) return daysOrder;
      return String(left?.title || '').localeCompare(String(right?.title || ''), 'tr');
    })
    .slice(0, Math.max(0, Number(limit) || 0));
}

export function workplaceDeadlineText(row) {
  const days = Number(row?.days_left);
  if (!Number.isFinite(days)) return 'Tarih bekleniyor';
  if (days < 0) return `${Math.abs(days)} gün gecikti`;
  if (days === 0) return 'Bugün';
  return `${days} gün kaldı`;
}

export function workplaceDateText(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ''));
  return match ? `${match[3]}.${match[2]}.${match[1]}` : (value || '—');
}

export function workplaceStatusTone(status) {
  if (status === 'critical') return 'critical';
  if (status === 'warning') return 'warning';
  return 'compliant';
}
