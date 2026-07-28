/** Acil durum krokisi — Türkiye mevzuat dayanakları (plan kenarı paneli). */

export const MEVZUAT_BLOCKS = [
  {
    id: 'kanun',
    title: '6331 sayılı İSG Kanunu',
    articles: [
      {ref: 'Madde 11', text: 'İşverenin acil durum planı hazırlama, tahliye ve müdahale yükümlülüğü.'},
      {ref: 'Madde 12', text: 'Çalışanların acil durumlara ilişkin bilgilendirilmesi ve tatbikat.'},
    ],
  },
  {
    id: 'acil_yonetmelik',
    title: 'İşyerlerinde Acil Durumlar Hakkında Yönetmelik',
    articles: [
      {ref: 'Md. 7–9', text: 'Acil durum planının hazırlanması, içeriği, gözden geçirme ve güncelleme.'},
      {ref: 'Md. 10–11', text: 'Acil durum ekipleri, görev dağılımı ve toplanma alanları.'},
      {ref: 'Md. 12', text: 'Tahliye ve tatbikatların planlanması / uygulanması.'},
    ],
  },
  {
    id: 'bina',
    title: 'İşyeri Bina ve Eklentileri Yönetmeliği',
    articles: [
      {ref: 'Kaçış yolları', text: 'Acil çıkış kapıları, merdivenler ve kaçış güzergâhlarının işaretlenmesi.'},
      {ref: 'İşaretleme', text: 'Acil durum işaretlerinin görünür, anlaşılır ve standartlara uygun olması.'},
    ],
  },
  {
    id: 'standart',
    title: 'İşaret / kroki standartları (TR uygulaması)',
    articles: [
      {ref: 'TS EN ISO 7010', text: 'Güvenlik işaretleri: renk, şekil ve piktogram (çıkış, yangın, ilk yardım).'},
      {ref: 'TS EN ISO 23601', text: 'Acil durum tahliye planı krokilerinde sembol ve lejant düzeni.'},
    ],
  },
];

/** Sembol tipine göre kısa dayanak satırı (özellik paneli). */
export const SYMBOL_LEGAL_HINT = {
  exit: 'ISO 7010 E001/E002 · Bina Yönetmeliği kaçış işaretleri',
  door_exit: 'Acil çıkış kapısı · kaçış yolu işaretleme',
  stairs: 'ISO 7010 E016/E017 · kaçış merdiveni',
  assembly: 'Acil Durumlar Yön. toplanma alanı',
  youarehere: 'ISO 23601 «Siz buradasınız»',
  route: 'ISO 23601 tahliye yönü / yeşil kaçış oku',
  extinguisher: 'ISO 7010 F001 · yangın söndürücü',
  hose: 'ISO 7010 F002 · yangın dolabı / hortum',
  alarm: 'ISO 7010 F005 · yangın alarmı',
  firstaid: 'İlk yardım — TR uygulamada hilal (Kızılay); yeşil güvenli durum zemini',
  aed: 'ISO 7010 EC010 · AED / defibrilatör',
  electric: 'Acil elektrik kesme noktası (tesisat)',
  room: 'Kat / mahal tanımlama (atölye, idare vb.)',
  wall: 'Yapı geometrisi (duvar)',
  door: 'Kapı (kaçış yolu üzerindeki geçiş)',
  north: 'Kuzey yönü (plan yönelimi)',
  text: 'Serbest açıklama / mahal adı',
};
