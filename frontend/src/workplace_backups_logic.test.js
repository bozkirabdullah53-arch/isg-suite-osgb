import {describe, expect, it} from 'vitest';
import {backupSourceLabel, backupStatusLabel, formatBackupSize, portableBackupFilename, workplaceBackupsEnabled} from './workplace_backups_logic';
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
  it('names encrypted archive downloads as standard zip files', () => {
    expect(portableBackupFilename('workplace-173.zip.enc', 173)).toBe('workplace-173.zip');
    expect(portableBackupFilename(null, 173)).toBe('isyeri-yedegi-173.zip');
  });
});
