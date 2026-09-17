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
  'workplace_home',
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
  'documents',
  'eyas_inbox',
  'health',
  'site_qr_kiosk',
]);

export const WORKPLACE_MENU_SECTIONS = Object.freeze([
  {label: 'İşyeri Özeti', items: ['workplace_home', 'employer_oversight']},
  {label: 'Personel', items: ['employees', 'personnel_training_records']},
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
  {label: 'İşyeri QR', items: ['site_qr_kiosk']},
]);

export function workplaceMenuSection(user, moduleId) {
  if (!isWorkplaceManagerUser(user)) return '';
  return WORKPLACE_MENU_SECTIONS.find((section) => section.items.includes(moduleId))?.label || '';
}
