/** İlk açılışta yıllık değerlendirme için erişilebilir firmayı belirler. */
export function chooseAnnualEvalCompanyId(companies, currentId = '', userCompanyId = '') {
  const rows = Array.isArray(companies) ? companies : [];
  const ids = new Set(rows.map((company) => String(company?.id ?? '')).filter(Boolean));
  const firstValid = [currentId, userCompanyId].find((value) => value != null && ids.has(String(value)));
  return firstValid != null ? String(firstValid) : (rows[0]?.id != null ? String(rows[0].id) : '');
}
