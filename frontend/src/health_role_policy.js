import {isWorkplaceManagerUser} from './workplace_user_policy';

/** Klinik kayıt oluşturma/değiştirme yetkisi yalnız sağlık profesyonellerindedir. */
export function canEditHealthRecords(user) {
  return ['workplace_physician', 'other_health_personnel'].includes(user?.role);
}

/** İşyeri yetkilisi yalnız veri-minimize, salt-okunur görünümü açabilir. */
export function canViewHealthRecords(user) {
  return canEditHealthRecords(user) || isWorkplaceManagerUser(user);
}

/** İşverene uygunluk belgesi hekim ve normal işyeri yetkilisine açıktır. */
export function canViewEmployerFitness(user) {
  return user?.role === 'workplace_physician' || isWorkplaceManagerUser(user);
}

/** Sağlık ekranının yalnız hekime ait analiz isteklerini belirler. */
export function canLoadHealthAnalysis(role) {
  return role === 'workplace_physician';
}
