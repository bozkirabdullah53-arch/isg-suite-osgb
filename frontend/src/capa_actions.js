export function canManageDof(user) {
  return ['global_admin', 'safety_specialist', 'workplace_physician'].includes(user?.role)
    || (user?.role === 'company_admin' && Boolean(user.company_id));
}

export function capaStatus(row) {
  if (row.is_completed) return {label: 'Tamamlandı', tone: 'badge-ok'};
  if (row.is_overdue) return {label: 'Gecikmiş', tone: 'badge-danger'};
  if (row.term_kind === 'continuous' && !row.term) return {label: 'Sürekli izleme', tone: 'badge-muted'};
  if (!row.term) return {label: 'Termin belirlenmedi', tone: 'badge-warn'};
  return {label: row.status || 'Açık', tone: 'badge-warn'};
}

export function formatCapaDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value || '') ? value.split('-').reverse().join('.') : value || '—';
}
