const FIELD_VISIT_ROLES = new Set([
  'safety_specialist',
  'workplace_physician',
  'other_health_personnel',
]);

/**
 * İşyeri QR giriş/çıkışı OSGB'ye bağlı saha profesyonellerine aittir.
 * Bireysel uzman çalışma alanları bu kiosk akışını kullanmaz.
 */
export function canUseVisitCheckInOutQr(user) {
  return FIELD_VISIT_ROLES.has(user?.role) && !Boolean(user?.is_individual);
}

/**
 * The QR link remains available to professionals when they have at least one
 * eligible workplace. The OSGB policy is evaluated again by the API.
 */
export function isVisitQrEnabledForCompany(company) {
  // Undefined is intentionally treated as enabled for old API responses.
  return company?.visit_qr_enabled !== false;
}

export function canUseVisitCheckInOutQrForCompany(user, company) {
  return canUseVisitCheckInOutQr(user) && isVisitQrEnabledForCompany(company);
}
