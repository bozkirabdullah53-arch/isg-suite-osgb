/** Menu visibility and an authorized company's read-only DÖF route are separate. */
export const COMPANY_CONTEXT_MODULES = new Set(['customer_360', 'workplace_status', 'capa']);

export function canOpenCompanyCapa(user, moduleId, companyId) {
  return user?.role === 'company_admin'
    && !user.company_id
    && moduleId === 'capa'
    && Number.isInteger(Number(companyId))
    && Number(companyId) > 0;
}
