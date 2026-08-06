import {describe, expect, it} from 'vitest';
import {
  buildPerformanceExcelDownload,
  replaceCsvLabel,
  reportStamp,
} from './professional_performance_excel_logic';

describe('professional performance Excel helpers', () => {
  it('builds OSGB roster Excel route and filename', () => {
    expect(buildPerformanceExcelDownload('roster', {osgbId: 35, stamp: '2026-08-06'})).toEqual({
      path: '/osgb/professionals/performance/export.xlsx?osgb_id=35',
      filename: 'csgb-profesyonel-performans-35-2026-08-06.xlsx',
    });
  });

  it('builds selected professional detail Excel route and filename', () => {
    expect(buildPerformanceExcelDownload('detail', {professionalId: 153, stamp: '2026-08-06'})).toEqual({
      path: '/osgb/professionals/153/performance/export.xlsx',
      filename: 'csgb-profesyonel-performans-detay-153-2026-08-06.xlsx',
    });
  });

  it('does not allow an ambiguous download without a scope', () => {
    expect(() => buildPerformanceExcelDownload('roster', {})).toThrow('OSGB seçimi bulunamadı.');
    expect(() => buildPerformanceExcelDownload('detail', {})).toThrow('Profesyonel seçimi bulunamadı.');
  });

  it('uses an ISO date stamp and converts only CSV labels', () => {
    expect(reportStamp(new Date('2026-08-06T03:00:00Z'))).toBe('2026-08-06');
    expect(replaceCsvLabel('Profesyonel performans CSV')).toBe('Profesyonel performans Excel');
    expect(replaceCsvLabel('OSGB CSV')).toBe('OSGB Excel');
    expect(replaceCsvLabel('Detay CSV')).toBe('Detay Excel');
    expect(replaceCsvLabel('ÇSGB belge paketi')).toBe('ÇSGB belge paketi');
  });
});
