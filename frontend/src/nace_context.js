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
    // NACE kimliği yalnızca kod/ASCII anahtarından oluşur. Locale dönüşümü
    // her tuş vuruşunda binlerce kez çalıştığı için özellikle Chrome'da
    // yazmayı gereksiz yere yavaşlatıyordu.
    .toLowerCase()
    .replace(/^nace[_-]?/, '')
    .replace(/[^a-z0-9]/g, '');
}

const naceIndexCache = new WeakMap();

function naceIndexFor(catalog) {
  const cached = naceIndexCache.get(catalog);
  if (cached) return cached;

  const index = new Map();
  catalog.forEach((item) => {
    [item?.code, item?.nace].forEach((candidate) => {
      const key = compactNace(candidate);
      if (key && !index.has(key)) index.set(key, item);
    });
  });
  naceIndexCache.set(catalog, index);
  return index;
}

export function findNaceRecord(catalog, value) {
  const raw = String(value || '').trim();
  if (!raw || !Array.isArray(catalog) || !catalog.length) return null;

  const candidates = new Set([compactNace(raw)]);
  const dotted = raw.match(/\d{2}(?:\.\d{2}){1,2}/)?.[0] || '';
  if (dotted) candidates.add(compactNace(dotted));

  const index = naceIndexFor(catalog);
  for (const candidate of candidates) {
    const match = index.get(candidate);
    if (match) return match;
  }
  return null;
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
