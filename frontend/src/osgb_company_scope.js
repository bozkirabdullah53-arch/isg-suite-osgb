export function osgbDashboardCompanyOptions(rows, {role, osgbId} = {}) {
  const active = (Array.isArray(rows) ? rows : []).filter((row) => row?.is_active !== false);

  // For non-global roles /companies is already authorization-scoped by the API.
  // Do not narrow it again using an OSGB id inferred from an unrelated list.
  if (role !== 'global_admin') return active;

  // A global administrator must choose a known OSGB before any company names
  // are exposed in this selector.
  if (!osgbId) return [];
  return active.filter((row) => String(row?.osgb_id) === String(osgbId));
}

export function osgbDashboardInitialOrganizationId(user, organizations = []) {
  // An OSGB user's company list is already scoped by /companies. If their
  // account has no organization id, leave the scope unresolved until they
  // select a company; the first /osgb row may belong to another organization.
  if (user?.role === 'company_admin') return String(user?.osgb_id || '');
  return String(user?.osgb_id || organizations?.[0]?.id || '');
}
