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

/**
 * İşyeri kullanıcısının günlük operasyon menüsü.
 * Sıra özellikle şu iş akışını öne çıkarır: personel → KKD → PKD → periyodik
 * kontrol → eğitim katılımı/belgelendirme.
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
  'eyas_inbox',
  'ortam_olcum',
  'accident',
  'near_miss',
  'security',
]);
