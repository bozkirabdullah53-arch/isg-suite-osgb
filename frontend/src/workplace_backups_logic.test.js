import {describe, expect, it} from 'vitest';
import {backupSourceLabel, backupStatusLabel, formatBackupSize, workplaceBackupsEnabled} from './workplace_backups_logic';
describe('workplace backup helpers', () => {
  it('keeps rollout fail closed', () => {
    expect(workplaceBackupsEnabled(undefined)).toBe(false);
    expect(workplaceBackupsEnabled('true')).toBe(true);
  });
  it('formats metadata for the workplace user', () => {
    expect(formatBackupSize(2048)).toBe('2.0 KB');
    expect(backupStatusLabel('completed')).toBe('Hazır');
    expect(backupSourceLabel('scheduled')).toBe('Otomatik');
  });
});
