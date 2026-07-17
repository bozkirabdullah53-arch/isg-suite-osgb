# Faz 4 Kullanım Rehberi

Bu paket Faz 1, Faz 2, Faz 3 ve Faz 4'ü tek proje içinde içerir.

## Eklenen modüller

- İşyeri hekimi sağlık ve muayene kayıtları
- İşe giriş ve periyodik muayene türleri
- Çalışmaya uygunluk durumu
- Sonraki muayene tarihi
- Gizli hekim notu alanı
- Doküman arşivi
- Doküman kategori, versiyon ve geçerlilik tarihleri
- Yıllık çalışma planı
- Yönetim KPI raporları

## Sağlık verisi güvenliği

Sağlık kayıtlarına yalnızca:

- Global yönetici
- İşyeri hekimi

rolleri erişebilir.

Firma yöneticisi ve iş güvenliği uzmanı sağlık kayıtlarını görüntüleyemez.

## Önemli sınır

Bu fazda dosya adı ve doküman meta verisi kaydedilir. Gerçek dosya yükleme,
antivirüs taraması, nesne depolama ve güvenli indirme bağlantıları sonraki fazda
eklenmelidir.

## Veritabanı

Yerel SQLite kullanılıyorsa eski geliştirme veritabanını silerek yeni tabloların
oluşturulması gerekir. Canlı sistemde Alembic migration kullanılmalıdır.
