export function workplaceBackupsEnabled(value) {
  return ['1', 'true', 'yes', 'on'].includes(String(value ?? '').trim().toLowerCase());
}
export function formatBackupSize(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
export function backupStatusLabel(status) {
  return {running: 'Hazırlanıyor', completed: 'Hazır', failed: 'Başarısız'}[status] || status || '—';
}
export function backupSourceLabel(source) {
  return source === 'scheduled' ? 'Otomatik' : 'Manuel';
}
export function portableBackupFilename(originalName, backupId) {
  const name = String(originalName || '').trim();
  if (!name) return `isyeri-yedegi-${backupId}.zip`;
  return name.toLowerCase().endsWith('.enc') ? name.slice(0, -4) : name;
}
