export function reportStamp(now = new Date()) {
  return now.toISOString().slice(0, 10);
}

export function buildPerformanceExcelDownload(kind, {osgbId, professionalId, stamp = reportStamp()} = {}) {
  if (kind === 'detail') {
    const id = Number(professionalId || 0);
    if (!id) throw new Error('Profesyonel seçimi bulunamadı.');
    return {
      path: `/osgb/professionals/${id}/performance/export.xlsx`,
      filename: `csgb-profesyonel-performans-detay-${id}-${stamp}.xlsx`,
    };
  }

  const oid = Number(osgbId || 0);
  if (!oid) throw new Error('OSGB seçimi bulunamadı.');
  return {
    path: `/osgb/professionals/performance/export.xlsx?osgb_id=${oid}`,
    filename: `csgb-profesyonel-performans-${oid}-${stamp}.xlsx`,
  };
}

export function replaceCsvLabel(text) {
  return String(text || '')
    .replace(/Profesyonel performans CSV/gi, 'Profesyonel performans Excel')
    .replace(/OSGB CSV/gi, 'OSGB Excel')
    .replace(/Detay CSV/gi, 'Detay Excel');
}
