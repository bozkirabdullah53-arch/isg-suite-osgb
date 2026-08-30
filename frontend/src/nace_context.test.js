import {describe, expect, it} from 'vitest';
import {
  augmentNaceCatalog,
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

  it('resolves legacy NACE codes without hardcoding the form field to one code', () => {
    const rows = augmentNaceCatalog([
      {
        code: 'nace_41_00_01',
        nace: '41.00.01',
        name: 'İkamet amaçlı binaların inşaatı',
        hazard_class: 'Çok Tehlikeli',
        topics: ['Yapı işleri', 'Yüksekte çalışma', 'İş ekipmanları', 'Acil durumlar', 'KKD'],
      },
    ]);
    expect(findNaceRecord(rows, '41.20.02')).toMatchObject({
      nace: '41.20.02',
      hazard_class: 'Çok Tehlikeli',
      is_legacy_alias: true,
      source_nace: '41.00.01',
    });
    expect(findNaceRecord(rows, '41.20.99')).toBeNull();
    expect(findNaceRecord(rows, '41.20.029')).toBeNull();
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
