/** Acil durum krokisi — Türkiye mevzuat dayanakları (plan kenarı paneli). */

export const MEVZUAT_BLOCKS = [
  {
    id: 'kanun',
    title: '6331 sayılı İSG Kanunu',
    articles: [
      {ref: 'Madde 11', text: 'Acil durum planı, ekipler ve destek elemanları için işveren yükümlülükleri.'},
      {ref: 'Madde 12', text: 'Ciddi ve yakın tehlike halinde çalışanların tahliyesi ve güvenli alana yönlendirilmesi.'},
    ],
  },
  {
    id: 'acil_yonetmelik',
    title: 'İşyerlerinde Acil Durumlar Hakkında Yönetmelik',
    articles: [
      {ref: 'Md. 5–8', text: 'Senaryoların belirlenmesi, önleyici tedbirler ve acil durum planının hazırlanması.'},
      {ref: 'Md. 10–12', text: 'Müdahale / tahliye, ekipler, planın asgari içeriği ve görünür biçimde bulundurulması.'},
      {ref: 'Md. 13–15', text: 'Tatbikat, planın yenilenmesi ve çalışanların bilgilendirilmesi.'},
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
      {ref: 'TS EN ISO 7010', text: 'Kullanılan işaretlerin renk, şekil ve piktogram referansı.'},
      {ref: 'TS EN ISO 23601', text: 'Kroki düzeni için referans; nihai işaret ve plan saha koşullarında doğrulanmalıdır.'},
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
