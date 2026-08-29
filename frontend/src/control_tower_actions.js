const ROLE_TARGETS = {
  action: {
    safety_specialist: {module: 'capa', label: 'DÖF ekranını aç'},
  },
  contractor: {
    safety_specialist: {module: 'contractors', label: 'Taşeronları aç'},
  },
  periodic: {
    safety_specialist: {module: 'periyodik_kontrol', label: 'Periyodik kontrolleri aç'},
  },
  ptw: {
    safety_specialist: {module: 'work_permits', label: 'Çalışma izinlerini aç'},
    other_health_personnel: {module: 'work_permits', label: 'Çalışma izinlerini aç'},
  },
  capacity: {
    company_admin: {module: 'capacity_engine', label: 'Kapasite Motorunu aç'},
    safety_specialist: {module: 'workplace_status', label: 'İşyeri durumunu aç'},
    other_health_personnel: {module: 'workplace_status', label: 'İşyeri durumunu aç'},
  },
};

/**
 * Control Tower yalnız mevcut modüllere güvenli bir kısayol üretir.
 * Bu katman kayıt değiştirmez ve kullanıcının rolünde bulunmayan bir hedefi
 * görünür kılmaz. Böylece mevcut bounded-context iş akışları kaynak olarak kalır.
 */
export function controlTowerActionFor(item, userRole) {
  const domain = String(item?.domain || '').trim();
  const role = String(userRole || '').trim();
  if (!domain || !role) return null;
  return ROLE_TARGETS[domain]?.[role] || null;
}

/**
 * Query tabanlı bağlantı bilinçli olarak kullanılır: uygulamanın mevcut
 * navigation_history sözleşmesi ?m=<module> biçimini destekler ve sayfa
 * yenilense bile sessionStorage tabanlı oturum korunur.
 */
export function controlTowerActionHref(item, userRole) {
  const action = controlTowerActionFor(item, userRole);
  return action ? `?m=${encodeURIComponent(action.module)}` : '';
}

/**
 * İşyeri bağlamı için uygulamanın zaten desteklediği Customer 360 sözleşmesini
 * kullanır. Yeni bir state/store veya ikinci işyeri seçimi mekanizması yaratmaz.
 * Geçersiz/manüel kimlikler için link üretmez; backend erişim kontrolü ayrıca
 * mevcut ensure_company_access katmanında kalır.
 */
export function controlTowerCompanyContextHref(companyId) {
  const id = Number(companyId);
  if (!Number.isInteger(id) || id <= 0) return '';
  return `?m=customer_360&company=${encodeURIComponent(String(id))}`;
}
