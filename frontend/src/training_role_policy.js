/** Klasik eğitim paketi ile operasyonel eğitim işlemlerini ayırır. */
const OPERATIONAL_ROLES = new Set([
  'global_admin',
  'company_admin',
  'safety_specialist',
]);

export function canOperateTraining(user) {
  return OPERATIONAL_ROLES.has(user?.role);
}

export function canManageTrainingPackage(user) {
  if (user?.role === 'global_admin') return true;
  return (
    user?.role === 'company_admin' &&
    Boolean(user?.osgb_id) &&
    user?.company_id == null
  );
}

/**
 * İSG uzmanı atanmış işyerindeki eğitim kaydını hazırlayabilir.
 * Backend ayrıca şirket erişimini doğrular; bu yardımcı tek başına kapsam
 * genişletmez ve OSGB geneli arşiv/silme yetkisini değiştirmez.
 */
export function canEditTrainingForm(user) {
  return canManageTrainingPackage(user) || user?.role === 'safety_specialist';
}
