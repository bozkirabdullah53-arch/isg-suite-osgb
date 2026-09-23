export function filterCompanyDirectoryRows(rows, {selectedCompanyId, selectionRequired = false} = {}) {
  const list = Array.isArray(rows) ? rows : [];
  if (!selectionRequired) return list;

  const selectedId = String(selectedCompanyId ?? '').trim();
  if (!selectedId) return [];

  return list.filter((row) => String(row?.id ?? '') === selectedId);
}
