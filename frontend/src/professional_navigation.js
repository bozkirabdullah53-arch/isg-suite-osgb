/**
 * İSG profesyonellerinin günlük iş akışına göre sol menü düzeni.
 *
 * Buradaki modül listeleri yalnızca mevcut modül anahtarlarını yeniden sıralar;
 * yeni bir yetki veya backend işlemi tanımlamaz. Böylece menü sadeleşirken
 * mevcut rol matrisi geriye dönük uyumlu kalır.
 */
export const PROFESSIONAL_MENU_SECTIONS = {
  safety_specialist: [
    {
      label: 'Günlük İş Akışı',
      items: [
        'dashboard',
        'visit_notebook',
        'visit_qr',
        'field_inspection',
        'risk',
        'capa',
        'employees',
        'visits',
        'field_pwa',
        'notifications',
      ],
    },
    {
      label: 'Olay, Ekipman ve Eğitim',
      items: [
        'ppe',
        'near_miss',
        'accident',
        'training',
        'eisa_question_bank',
        'belge_onay',
      ],
    },
    {
      label: 'Planlama ve Uyum',
      items: [
        'workplace_status',
        'facility_summary',
        'acil_plan',
        'acil_ekipler',
        'tatbikat',
        'periyodik_kontrol',
        'ortam_olcum',
        'isg_kurulu',
        'sds',
        'annual_plans',
        'annual_eval_report',
        'documents',
        'work_permits',
        'contractors',
        'visitors',
        'customer_portal',
      ],
    },
    {
      label: 'Raporlar ve Sistem',
      items: ['specialist_reports', 'mevzuat', 'security'],
    },
  ],
  workplace_physician: [
    {
      label: 'Günlük İş Akışı',
      items: [
        'dashboard',
        'health',
        'prescriptions',
        'visit_notebook',
        'visit_qr',
        'employees',
        'visits',
      ],
    },
    {
      label: 'Onay ve Uyum',
      items: ['belge_onay', 'eyas_inbox', 'workplace_status', 'ortam_olcum', 'training'],
    },
    {
      label: 'Planlama ve Kayıtlar',
      items: ['annual_plans', 'annual_eval_report', 'documents'],
    },
    {
      label: 'Sistem',
      items: ['security'],
    },
  ],
};

export const PROFESSIONAL_MENU_MODULES = Object.fromEntries(
  Object.entries(PROFESSIONAL_MENU_SECTIONS).map(([role, sections]) => [
    role,
    sections.flatMap((section) => section.items),
  ]),
);

export function professionalModulesForUser(role, {isIndividual = false} = {}) {
  const modules = PROFESSIONAL_MENU_MODULES[role] || [];
  if (!isIndividual) return modules;
  return modules.filter((moduleId) => {
    if (moduleId === 'visit_qr') return false;
    if (moduleId === 'belge_onay' || moduleId === 'eyas_inbox') return false;
    if (role === 'safety_specialist' && moduleId === 'customer_portal') return false;
    return true;
  });
}

export function professionalMenuSection(role, moduleId) {
  return PROFESSIONAL_MENU_SECTIONS[role]?.find((section) => section.items.includes(moduleId))?.label || '';
}

export function professionalHomeModule(role, allowedModules = []) {
  const requestedRoles = new Set(['safety_specialist', 'workplace_physician']);
  return requestedRoles.has(role) && allowedModules.includes('dashboard') ? 'dashboard' : '';
}
