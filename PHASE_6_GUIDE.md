# Faz 6 Kullanım Rehberi

Bu paket Faz 1–6'nın tamamını tek proje içinde içerir.

## Eklenen özellikler

- Firma bazlı abonelik ve paket modeli
- 14 günlük otomatik demo aboneliği
- Demo, Başlangıç, Profesyonel ve Kurumsal paketler
- Kullanıcı ve personel kota alanları
- Abonelik durumları
- Bildirim merkezi
- Termin tarihi geçen İSG kayıtları
- Süresi yaklaşan veya geçen dokümanlar
- Yaklaşan sağlık muayeneleri
- Geciken yıllık plan faaliyetleri
- Bildirimi okundu işaretleme
- Sistem sağlık kontrolü
- Basit API rate limiting
- Faz 6 kullanıcı arayüzleri

## Bildirim üretme

Firma kullanıcısı Bildirimler ekranındaki **Süreleri Kontrol Et** düğmesine basarak
mevcut kayıtları yeniden taratabilir.

Canlı sistemde bu işlem zamanlanmış görev ile her gece otomatik çalıştırılmalıdır.

## Abonelik

Yeni firma için abonelik ilk sorguda otomatik oluşturulur:

- Paket: Demo
- Durum: Deneme
- Süre: 14 gün
- Kullanıcı kotası: 3
- Personel kotası: 50

Bu fazda ödeme tahsilatı yapılmaz. Stripe, iyzico veya başka bir ödeme sağlayıcısı
ayrı entegrasyon ve hukuki değerlendirme sonrasında bağlanmalıdır.

## Üretim notları

Bellek içi rate limiter tek sunuculu temel korumadır. Çoklu sunucuda Redis tabanlı
rate limiting kullanılmalıdır.

Bildirimleri otomatik üretmek için Celery, RQ, APScheduler veya platform cron
servisi kullanılmalıdır.
