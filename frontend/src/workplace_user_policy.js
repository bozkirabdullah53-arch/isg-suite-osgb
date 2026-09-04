/**
 * ``company_admin`` iki farklı hesabı temsil eder:
 * - company_id yoksa OSGB yöneticisi
 * - company_id varsa tek işyerine bağlı işyeri yetkilisi
 *
 * QR kiosk hesabı operasyonel panel değildir ve bu yetkilerden özellikle hariçtir.
 */
export function isWorkplaceKioskUser(user) {
  if (user?.role !== 'company_admin' || !user.company_id) return false;
  return String(user.email || '').toLowerCase().endsWith('@kiosk.isgsuite.tr');
}

export function isWorkplaceManagerUser(user) {
  return user?.role === 'company_admin'
    && Number(user.company_id) > 0
    && !isWorkplaceKioskUser(user);
}

export const WORKPLACE_MANAGER_MODULES = Object.freeze([
  'employer_oversight',
  'eyas_inbox',
  'employees',
  'personnel_training_records',
  'ppe',
  'periyodik_kontrol',
  'ortam_olcum',
  'sds',
  'accident',
  'near_miss',
  'security',
]);
