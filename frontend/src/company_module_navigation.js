/** Menu visibility and an authorized company's read-only DÖF route are separate. */
export const COMPANY_CONTEXT_MODULES = new Set(['customer_360', 'workplace_status', 'capa', 'osgb_dashboard']);

// Company keys are positive decimal database IDs. An empty selection is not 0.
export function normalizeCompanyId(value) {
  if (typeof value !== 'string' && typeof value !== 'number') return '';
  const text = String(value).trim();
  const number = Number(text);
  return /^\d+$/.test(text) && Number.isSafeInteger(number) && number > 0 ? String(number) : '';
}

export function canOpenCompanyCapa(user, moduleId, companyId) {
  return user?.role === 'company_admin'
    && !user.company_id
    && moduleId === 'capa'
    // The empty route shows only the picker; it grants no company/data access.
    && (companyId == null || companyId === '' || Boolean(normalizeCompanyId(companyId)));
}
