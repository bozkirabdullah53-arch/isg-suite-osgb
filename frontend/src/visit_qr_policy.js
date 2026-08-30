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
