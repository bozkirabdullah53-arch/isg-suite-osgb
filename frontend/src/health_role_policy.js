import {isWorkplaceAccountUser} from './workplace_user_policy';

/** Klinik kayıt oluşturma/değiştirme yetkisi yalnız sağlık profesyonellerindedir. */
export function canEditHealthRecords(user) {
  return ['workplace_physician', 'other_health_personnel'].includes(user?.role);
}

/** Mevcut işyeri girişi yalnız veri-minimize, salt-okunur görünümü açabilir. */
export function canViewHealthRecords(user) {
  return canEditHealthRecords(user) || isWorkplaceAccountUser(user);
}

/** İşverene uygunluk belgesi hekim ve işyerine bağlı hesaba açıktır. */
export function canViewEmployerFitness(user) {
  return user?.role === 'workplace_physician' || isWorkplaceAccountUser(user);
}

/** Sağlık ekranının yalnız hekime ait analiz isteklerini belirler. */
export function canLoadHealthAnalysis(role) {
  return role === 'workplace_physician';
}
