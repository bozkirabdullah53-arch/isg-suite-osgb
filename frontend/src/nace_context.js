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

// NACE Rev.2'nin önceki yayımlarında 41.20.xx olarak kullanılan yapı
// faaliyetleri, güncel katalogda 41.00.xx altında yer alır. Bu küçük uyum
// katmanı yalnızca eski kodları güncel satıra bağlar; tüm diğer NACE'ler
// katalogdaki kendi tam kodlarıyla çözülür.
export const LEGACY_NACE_ALIASES = Object.freeze([
  Object.freeze({
    nace: '41.20.01',
    current_nace: '41.00.02',
    name: 'İkamet amaçlı olmayan binaların inşaatı (fabrika, atölye, hastane, okul, otel, işyeri ve benzeri binaların inşaatı)',
  }),
  Object.freeze({
    nace: '41.20.02',
    current_nace: '41.00.01',
    name: 'İkamet amaçlı binaların inşaatı (müstakil konutlar, birden çok ailenin oturduğu binalar, gökdelenler vb.nin inşaatı) (ahşap binaların inşaatı hariç)',
  }),
  Object.freeze({
    nace: '41.20.03',
    current_nace: '41.00.05',
    name: 'Prefabrik binalar için bileşenlerin alanda birleştirilmesi ve kurulması',
  }),
  Object.freeze({
    nace: '41.20.04',
    current_nace: '41.00.04',
    name: 'İkamet amaçlı ahşap binaların inşaatı',
  }),
  Object.freeze({
    nace: '41.20.05',
    current_nace: '41.00.03',
    name: 'Mevcut ikamet amaçlı olan veya ikamet amaçlı olmayan binaların yeniden düzenlenmesi veya yenilenmesi',
  }),
]);

const legacyNaceAliasIndex = new Map(
  LEGACY_NACE_ALIASES.map((item) => [compactNace(item.nace), item]),
);

function legacyAliasRow(alias, current) {
  const hazardClass = alias.hazard_class || current?.hazard_class || 'Çok Tehlikeli';
  return {
    ...(current || {}),
    code: `nace_${alias.nace.replace(/\./g, '_')}`,
    nace: alias.nace,
    name: alias.name,
    label: `${alias.nace} / ${alias.name} / ${hazardClass}`,
    hazard_class: hazardClass,
    topics: Array.isArray(current?.topics) ? current.topics : [],
    is_legacy_alias: true,
    source_nace: alias.current_nace,
  };
}

/**
 * Add known legacy aliases once, while keeping the official catalog rows
 * untouched. The returned array is safe to cache and share between screens.
 */
export function augmentNaceCatalog(catalog) {
  if (!Array.isArray(catalog) || !catalog.length) return catalog || [];

  const existing = new Set();
  const byCode = new Map();
  catalog.forEach((item) => {
    [item?.code, item?.nace].forEach((candidate) => {
      const key = compactNace(candidate);
      if (key) {
        existing.add(key);
        if (!byCode.has(key)) byCode.set(key, item);
      }
    });
  });

  const aliases = [];
  LEGACY_NACE_ALIASES.forEach((alias) => {
    const aliasKey = compactNace(alias.nace);
    if (existing.has(aliasKey)) return;
    const current = byCode.get(compactNace(alias.current_nace));
    aliases.push(legacyAliasRow(alias, current));
    existing.add(aliasKey);
  });
  return aliases.length ? [...catalog, ...aliases] : catalog;
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

  // The UI may be resolving a cached catalog from before the compatibility
  // rows were appended. Resolve the legacy code without a scan or a fuzzy
  // match, and keep the exact code the user entered visible.
  for (const candidate of candidates) {
    const alias = legacyNaceAliasIndex.get(candidate);
    if (alias) {
      return legacyAliasRow(alias, index.get(compactNace(alias.current_nace)));
    }
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

export function readPersistedCompanyId() {
  try {
    return String(sessionStorage.getItem('isg_selected_company_id') || '');
  } catch {
    return '';
  }
}

export function persistSelectedCompanyId(id) {
  try {
    const value = String(id || '');
    if (value) sessionStorage.setItem('isg_selected_company_id', value);
    else sessionStorage.removeItem('isg_selected_company_id');
  } catch {
    /* ignore */
  }
}

export function isNaceField(element) {
  if (!element || !['input', 'textarea'].includes(String(element.tagName || '').toLowerCase())) {
    return false;
  }
  return /nace/i.test(fieldContextText(element));
}
