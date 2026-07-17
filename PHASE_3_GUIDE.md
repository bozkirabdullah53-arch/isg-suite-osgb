# Faz 3 Kullanım Rehberi

Bu paket Faz 1, Faz 2 ve Faz 3'ü tek proje içinde içerir.

## Eklenen modüller

- Risk değerlendirmesi
- Ramak kala kayıtları
- İş kazası kayıtları
- Düzeltici ve önleyici faaliyetler (DÖF)
- Eğitim yönetimi

## Temel özellikler

- Firma ve şube bağlantısı
- Başlık, açıklama, olay tarihi ve termin tarihi
- Sorumlu kişi ve durum takibi
- Risklerde 1–5 olasılık ve şiddet üzerinden otomatik puan
- Eğitimlerde katılımcı sayısı
- Kayıt arama ve tamamlama
- Firma bazlı veri izolasyonu

## Veritabanı notu

SQLite ile Faz 2 daha önce çalıştırıldıysa geliştirme ortamındaki `isgsuite.db`
dosyasını silin. Uygulama yeni tabloları temiz biçimde oluşturacaktır.

Canlı sistemde Alembic migration kullanılmalıdır.
