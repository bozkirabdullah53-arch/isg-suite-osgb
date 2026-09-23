export function osgbDashboardCompanyOptions(rows, {role, osgbId} = {}) {
  const active = (Array.isArray(rows) ? rows : []).filter((row) => row?.is_active !== false);

  // A global administrator must choose a known OSGB before any company names
  // are exposed in this selector. Other roles receive only the companies the
  // API has already authorized for their account, even if their OSGB context
  // is missing from the user record.
  if (role === 'global_admin' && !osgbId) return [];
  if (!osgbId) return active;

  return active.filter((row) => String(row?.osgb_id) === String(osgbId));
}
