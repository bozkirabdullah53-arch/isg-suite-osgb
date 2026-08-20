/** Sağlık ekranının yalnız hekime ait analiz isteklerini belirler. */
export function canLoadHealthAnalysis(role) {
  return role === 'workplace_physician';
}
