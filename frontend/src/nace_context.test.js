import {describe, expect, it} from 'vitest';
import {
  compactNace,
  findNaceRecord,
  isCompanySelector,
  isNaceField,
  naceInfoForCompany,
} from './nace_context';

const catalog = [
  {
    code: 'nace_46_83_06',
    nace: '46.83.06',
    name: 'Metal yapı elemanlarının toptan ticareti',
    hazard_class: 'Tehlikeli',
  },
];

describe('NACE context helpers', () => {
  it('normalizes dotted and prefixed NACE values', () => {
    expect(compactNace('NACE 46.83.06')).toBe('468306');
    expect(compactNace('nace_46_83_06')).toBe('468306');
  });

  it('resolves a catalog row by official code or catalog key', () => {
    expect(findNaceRecord(catalog, '46.83.06')?.name).toContain('Metal yapı');
    expect(findNaceRecord(catalog, 'nace_46_83_06')?.nace).toBe('46.83.06');
    expect(findNaceRecord(catalog, '99.99.99')).toBeNull();
  });

  it('prefers the official catalog hazard class', () => {
    expect(naceInfoForCompany({
      nace_code: '46.83.06',
      hazard_class: 'Az Tehlikeli',
    }, catalog)).toMatchObject({
      code: '46.83.06',
      activity: 'Metal yapı elemanlarının toptan ticareti',
      hazardClass: 'Tehlikeli',
    });
  });

  it('recognizes company and NACE form controls', () => {
    document.body.innerHTML = '<label><span>İşyeri</span><select aria-label="İşyeri"><option value="1">A</option></select></label><label><span>NACE Kodu</span><input placeholder="NACE kodu" /></label>';
    expect(isCompanySelector(document.querySelector('select'))).toBe(true);
    expect(isNaceField(document.querySelector('input'))).toBe(true);
  });
});
