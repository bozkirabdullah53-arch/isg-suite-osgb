import {describe, expect, it} from 'vitest';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';

const customer360Source = readFileSync(join(process.cwd(), 'src/customer_360.jsx'), 'utf8');

describe('customer 360 Turkish UI encoding', () => {
  it('keeps Turkish labels as UTF-8 instead of mojibake', () => {
    expect(customer360Source).not.toMatch(/(?:Ã.|Ä.|Å.|Â.|â[€‚]|[\u009d]|�)/u);
    expect(customer360Source).toContain('Eksikler, tamamlanan süreçler ve sorumlular');
    expect(customer360Source).toContain('Modüle git');
    expect(customer360Source).toContain('Sanal Müfettiş');
    expect(customer360Source).toContain('6331 sayılı Kanun');
    expect(customer360Source).toContain('Önem');
    expect(customer360Source).toContain('Başlık');
  });
});
