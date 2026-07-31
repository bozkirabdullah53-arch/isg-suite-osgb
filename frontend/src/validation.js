/** Ortak tarih / metin doğrulama — saçma veya tutarsız giriş engeli (TR mesaj). */

const PLACEHOLDERS = new Set([
  'test', 'asdf', 'qwerty', 'xxx', 'xxxx', 'aaaa', 'bbbb',
  'yok', 'yok.', 'bilmiyorum', 'bilmiyorum.', '---', '...', 'n/a', 'na',
  'deneme', 'ornek', 'örnek', 'placeholder', 'string', 'null', 'none',
]);

export function cleanText(v) {
  if (v == null) return '';
  return String(v).replace(/\s+/g, ' ').trim();
}

export function isMeaningfulText(v, {minLen = 2, allowDigitsOnly = false} = {}) {
  const t = cleanText(v);
  if (!t || t.length < minLen) return false;
  const low = t.toLocaleLowerCase('tr-TR');
  if (PLACEHOLDERS.has(low)) return false;
  if (/^(.)\1{4,}$/.test(t)) return false;
  if (/^[\W_]+$/u.test(t)) return false;
  if (!allowDigitsOnly && /^\d+$/.test(t)) return false;
  return true;
}

export function isPersonName(v) {
  const t = cleanText(v);
  if (!t || t.length < 2) return false;
  if (PLACEHOLDERS.has(t.toLocaleLowerCase('tr-TR'))) return false;
  if (/^\d+$/.test(t)) return false;
  return /^[A-Za-zÀ-ÖØ-öø-ÿĞğÜüŞşİıÇçÖö][A-Za-zÀ-ÖØ-öø-ÿĞğÜüŞşİıÇçÖö\s.'-]{1,158}$/.test(t);
}

/** YYYY-MM-DD; gelecek yok, 2000'den önce yok */
export function isSensiblePastDate(v, {allowFutureDays = 0} = {}) {
  const t = cleanText(v);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) return false;
  const d = new Date(`${t}T12:00:00`);
  if (Number.isNaN(d.getTime())) return false;
  const floor = new Date('2000-01-01T12:00:00');
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const ceiling = new Date(today);
  ceiling.setDate(ceiling.getDate() + Math.max(0, allowFutureDays));
  return d >= floor && d <= ceiling;
}

export function assertIncidentForm(form) {
  if (!form.company_id) return 'Firma seçiniz.';
  if (!form.event_type) return 'Olay tipi seçiniz.';
  if (!form.event_date) return 'Olay tarihi zorunludur.';
  if (!isSensiblePastDate(form.event_date)) {
    return 'Olay tarihi geçerli olmalıdır (2000 sonrası, gelecek olamaz).';
  }
  if (!isMeaningfulText(form.location, {minLen: 2})) return 'Olay yeri için anlamlı bir metin giriniz.';
  if (!form.classification) return 'Sınıflandırma seçiniz.';
  if (!isMeaningfulText(form.short_summary, {minLen: 20})) {
    return 'Kısa özet en az 20 karakter ve anlamlı olmalıdır.';
  }
  if (!isMeaningfulText(form.detail, {minLen: 30})) {
    return 'Detay en az 30 karakter ve anlamlı olmalıdır (olayın nasıl geliştiğini yazın).';
  }
  if (form.has_witness && !isMeaningfulText(form.witness_names, {minLen: 3})) {
    return 'Şahit işaretliyse şahit isimlerini giriniz.';
  }
  for (const [key, label] of [
    ['safety_specialist', 'İSG uzmanı'],
    ['workplace_physician', 'İşyeri hekimi'],
    ['employer_representative', 'İşveren / vekili'],
    ['recorded_by_name', 'Kaydeden'],
  ]) {
    const v = cleanText(form[key]);
    if (v && !isPersonName(v)) return `${label} geçerli bir ad soyad olmalıdır.`;
  }
  if (form.sgk_reported && !form.sgk_report_date) {
    return 'SGK bildirildi işaretliyse bildirim tarihi girilmelidir.';
  }
  if (form.sgk_report_date) {
    if (!isSensiblePastDate(form.sgk_report_date)) {
      return 'SGK bildirim tarihi geçerli olmalıdır.';
    }
    if (form.sgk_report_date < form.event_date) {
      return 'SGK bildirim tarihi, olay tarihinden önce olamaz.';
    }
  }
  return '';
}
