/**
 * ``company_admin`` iki farklı kullanım alanını temsil eder:
 * - company_id yoksa OSGB yöneticisi
 * - company_id varsa tek işyerine bağlı işyeri yetkilisi
 *
 * Mevcut QR hesabı da kendi şirketine bağlı işyeri hesabıdır. Bu nedenle QR
 * erişimi korunurken aynı hesap işyeri operasyon paneline de erişebilir.
 */
export function isWorkplaceKioskUser(user) {
  if (user?.role !== 'company_admin' || !user.company_id) return false;
  return String(user.email || '').toLowerCase().endsWith('@kiosk.isgsuite.tr');
}

export function isWorkplaceManagerUser(user) {
  return user?.role === 'company_admin'
    && Number(user.company_id) > 0;
}

/**
 * İşyeri kullanıcısının günlük operasyon menüsü.
 *
 * Mevcut modüller yeniden yazılmaz; yalnızca zaten çalışan modüller işyeri
 * hesabına tenant kapsamı içinde görünür hale getirilir.
 *
 * Görüntüleme amaçlı modüller de aynı mevcut sayfaları kullanır; işlem
 * yetkileri ilgili mevcut rol kontrolleri tarafından belirlenir.
 */
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
]);
