function localIsoDate(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function effectiveAssignmentStatus(assignment, today = localIsoDate()) {
  const status = assignment?.status || 'active';
  if (status !== 'active') return status;
  if (assignment?.start_date && assignment.start_date > today) return 'planned';
  if (assignment?.end_date && assignment.end_date < today) return 'expired';
  return 'active';
}
