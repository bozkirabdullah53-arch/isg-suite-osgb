export function canViewExposurePeople(user) {
  return ['global_admin', 'safety_specialist', 'workplace_physician'].includes(user?.role)
    || (user?.role === 'company_admin' && Number(user?.company_id) > 0);
}

export function matchedWorkerCount(item) {
  return Number(item?.matched_worker_count ?? item?.exposed_worker_count ?? 0);
}

export function scopedMatches(employee, riskId = '') {
  return (employee.matches || []).filter((match) => !riskId || String(match.risk_id) === String(riskId));
}

export function visibleExposurePeople(data, {riskId = '', query = '', includeUnmatched = false} = {}) {
  const needle = query.trim().toLocaleLowerCase('tr');
  return (data?.employees || []).filter((person) => {
    if (!includeUnmatched && !scopedMatches(person, riskId).length) return false;
    return !needle || `${person.full_name || ''} ${person.department || ''} ${person.job_title || ''}`.toLocaleLowerCase('tr').includes(needle);
  });
}

export function validSelectedIds(data, selected) {
  const allowed = new Set((data?.employees || []).map((person) => Number(person.id)));
  return [...new Set(selected.map(Number))].filter((id) => allowed.has(id));
}

function csvCell(value) {
  let text = String(value ?? '');
  if (/^[\s]*[=+@-]/.test(text) || /^[\t\r\n]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

export function exposureTrainingCsv(data, selectedIds, riskId = '') {
  const selected = new Set(validSelectedIds(data, selectedIds));
  const risks = new Map((data.risks || []).map((risk) => [risk.id, risk]));
  const scopeRisk = risks.get(Number(riskId));
  const rows = [['İşyeri', 'Eğitim kapsamı', 'Ad soyad', 'Bölüm', 'Görev', 'İlgili riskler', 'Seçim dayanağı']];
  for (const person of data.employees || []) {
    if (!selected.has(Number(person.id))) continue;
    const matches = scopedMatches(person, riskId);
    rows.push([data.company.name, scopeRisk?.hazard || data.scope.label, person.full_name,
      person.department, person.job_title,
      matches.map((match) => { const risk = risks.get(match.risk_id); return `${risk?.risk_code || ''}: ${risk?.hazard || ''} — ${risk?.risk_definition || ''}`; }).join(' | '),
      matches.length ? [...new Set(matches.flatMap((match) => match.reasons))].join(' | ') : 'Manuel eğitim seçimi; otomatik maruziyet eşleşmesi yok',
    ]);
  }
  return '\uFEFF' + rows.map((row) => row.map(csvCell).join(';')).join('\r\n');
}
