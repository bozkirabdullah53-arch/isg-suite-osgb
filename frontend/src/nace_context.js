/**
 * NACE katalog değerlerini ekranlar arasında aynı biçimde çözümlemek için
 * küçük, bağımsız yardımcılar.
 *
 * Katalogdaki resmî faaliyet adı ve tehlike sınıfı tek kaynak olarak kullanılır.
 * Eski firma kayıtlarında yalnızca NACE kodu bulunması da desteklenir.
 */

export function compactNace(value) {
  return String(value || '')
    .trim()
    .toLocaleLowerCase('tr-TR')
    .replace(/^nace[_-]?/, '')
    .replace(/[^a-z0-9]/g, '');
}

export function findNaceRecord(catalog, value) {
  const raw = String(value || '').trim();
  if (!raw || !Array.isArray(catalog) || !catalog.length) return null;

  const candidates = new Set([compactNace(raw)]);
  const dotted = raw.match(/\d{2}(?:\.\d{2}){1,2}/)?.[0] || '';
  if (dotted) candidates.add(compactNace(dotted));

  return catalog.find((item) =>
    [item?.code, item?.nace].some((candidate) => candidates.has(compactNace(candidate))),
  ) || null;
}

export function naceInfoForCompany(company, catalog) {
  const code = String(company?.nace_code || '').trim();
  const match = findNaceRecord(catalog, code);
  return {
    code: match?.nace || code,
    activity: match?.name || '',
    hazardClass: match?.hazard_class || String(company?.hazard_class || '').trim(),
    match,
  };
}

export function fieldContextText(element) {
  if (!element) return '';
  const label = element.closest?.('label');
  return [
    label?.textContent,
    element.getAttribute?.('aria-label'),
    element.getAttribute?.('placeholder'),
    element.getAttribute?.('name'),
  ].filter(Boolean).join(' ');
}

export function isCompanySelector(element) {
  if (!element || String(element.tagName || '').toLowerCase() !== 'select') return false;
  return /(?:firma|işyeri|çalışma\s*yeri|workplace)/.test(
    fieldContextText(element).toLocaleLowerCase('tr-TR'),
  );
}

export function isNaceField(element) {
  if (!element || !['input', 'textarea'].includes(String(element.tagName || '').toLowerCase())) {
    return false;
  }
  return /nace/i.test(fieldContextText(element));
}
