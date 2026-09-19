/**
 * ``company_admin`` iki farklı kullanım alanını temsil eder:
 * - company_id yoksa OSGB yöneticisi
 * - company_id varsa tek işyerine bağlı işyeri yetkilisi
 */
export function isWorkplaceAccountUser(user) {
  return user?.role === 'company_admin'
    && Number(user.company_id) > 0;
}

export function isWorkplaceKioskUser(user) {
  return isWorkplaceAccountUser(user)
    && String(user.email || '').toLowerCase().endsWith('@kiosk.isgsuite.tr');
}

export function isWorkplaceManagerUser(user) {
  return isWorkplaceAccountUser(user)
    && !isWorkplaceKioskUser(user);
}

// Mevcut işyeri/QR şifresiyle açılan hesapların operasyon menüsü.
// OSGB yönetimi ve normal yetkili hesabının ek modülleri bu listeye dahil değildir.
export const WORKPLACE_KIOSK_MODULES = Object.freeze([
  'workplace_home', 'employer_oversight', 'employees', 'ppe', 'sds',
  'periyodik_kontrol', 'ortam_olcum', 'near_miss', 'accident', 'capa',
  'isg_kurulu', 'workplace_backups', 'site_qr_kiosk',
]);

export const WORKPLACE_MANAGER_MODULES = Object.freeze([
  'workplace_home',
  'workplace_status',
  'employer_oversight',
  'employees',
  'ppe',
  'sds',
  'periyodik_kontrol',
  'ortam_olcum',
  'near_miss',
  'accident',
  'capa',
  'isg_kurulu',
  'personnel_training_records',
  'remote_training',
  'documents',
  'eyas_inbox',
  'health',
  'workplace_backups',
  'site_qr_kiosk',
]);

export const WORKPLACE_MENU_SECTIONS = Object.freeze([
  {label: 'İşyeri Özeti', items: ['workplace_home', 'workplace_status', 'employer_oversight']},
  {label: 'Personel ve Eğitim', items: ['employees', 'personnel_training_records', 'remote_training']},
  {
    label: 'İSG Kayıtları',
    items: [
      'ppe',
      'sds',
      'periyodik_kontrol',
      'ortam_olcum',
      'near_miss',
      'accident',
      'capa',
      'isg_kurulu',
    ],
  },
  {label: 'Belgeler ve Onay', items: ['documents', 'eyas_inbox']},
  {label: 'Sağlık', items: ['health']},
  {label: 'Veri Güvenliği', items: ['workplace_backups']},
  {label: 'İşyeri QR', items: ['site_qr_kiosk']},
]);

export function workplaceMenuSection(user, moduleId) {
  if (!isWorkplaceAccountUser(user)) return '';
  return WORKPLACE_MENU_SECTIONS.find((section) => section.items.includes(moduleId))?.label || '';
}

export function workplaceModulesForUser(user) {
  if (!isWorkplaceAccountUser(user)) return null;
  return [...(isWorkplaceKioskUser(user) ? WORKPLACE_KIOSK_MODULES : WORKPLACE_MANAGER_MODULES)];
}
