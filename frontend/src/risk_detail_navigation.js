/**
 * Risk detay rotasında yalnızca pozitif, tam sayı kayıt kimliklerini kabul et.
 * URL ve liste yanıtları string/numeric karışık gelebileceği için karşılaştırma
 * tek bir normalize edilmiş biçimde yapılır.
 */
export function normalizeRiskId(value) {
  if (value == null || String(value).trim() === '') return null;
  const id = Number(value);
  return Number.isInteger(id) && id > 0 ? id : null;
}

export function isMatchingRiskId(actual, expected) {
  const actualId = normalizeRiskId(actual);
  const expectedId = normalizeRiskId(expected);
  return actualId !== null && actualId === expectedId;
}
