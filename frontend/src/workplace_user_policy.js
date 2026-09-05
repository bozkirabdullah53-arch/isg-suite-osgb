/**
 * ``company_admin`` iki farklı kullanım alanını temsil eder:
 * - company_id yoksa OSGB yöneticisi
 * - company_id varsa tek işyerine bağlı işyeri yetkilisi
 */
export function isWorkplaceKioskUser(user) {
  return user?.role === 'company_admin'
    && Number(user.company_id) > 0
    && String(user.email || '').toLowerCase().endsWith('@kiosk.isgsuite.tr');
}

export function isWorkplaceManagerUser(user) {
  return user?.role === 'company_admin'
    && Number(user.company_id) > 0
    && !isWorkplaceKioskUser(user);
}

export const WORKPLACE_MANAGER_MODULES = Object.freeze([
  'employer_oversight',
  'employees',
  'ppe',
  'sds',
  'periyodik_kontrol',
  'personnel_training_records',
  'documents',
  'eyas_inbox',
  'ortam_olcum',
  'accident',
  'near_miss',
  'health',
  'site_qr_kiosk',
]);
