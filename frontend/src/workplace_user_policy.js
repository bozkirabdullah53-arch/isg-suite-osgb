/**
 * ``company_admin`` iki farklı kullanım alanını temsil eder:
 * - company_id yoksa OSGB yöneticisi
 * - company_id varsa tek işyerine bağlı işyeri yetkilisi
 *
 * Mevcut QR hesabı da kendi şirketine bağlı işyeri hesabıdır. Bu nedenle QR
 * erişimi korunurken aynı hesap işyeri operasyon paneline de erişebilir.
 */
export function isWorkplaceKioskUser(user) {
  // QR hesabı artık ayrı bir kullanıcı tipi gibi yönlendirilmez; mevcut
  // işyeri hesabı operasyon paneline de girebilir ve QR modülü menüden açılır.
  return false;
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
  // Nihai operasyon listesine ek bir modül değildir; mevcut QR erişiminin
  // geriye dönük korunması için aynı hesapta tutulur.
  'site_qr_kiosk',
]);

/** İşyeri hesabında yalnız görüntülenebilen modüller. */
export const WORKPLACE_MANAGER_READONLY_MODULES = Object.freeze([
  'employer_oversight',
  'personnel_training_records',
  'documents',
  'health',
]);

/** İşyeri hesabında veri girişi / işlem yapılabilen modüller. */
export const WORKPLACE_MANAGER_EDITABLE_MODULES = Object.freeze([
  'employees',
  'ppe',
  'sds',
  'periyodik_kontrol',
  'eyas_inbox',
  'ortam_olcum',
  'accident',
  'near_miss',
]);

export function isWorkplaceModuleReadOnly(user, moduleId) {
  return isWorkplaceManagerUser(user)
    && WORKPLACE_MANAGER_READONLY_MODULES.includes(String(moduleId || ''));
}
