# Eğitim Premium Dashboard v1 — “Bugün Ne Yapmalıyım?”

## Amaç

Eğitim bölümünde kullanıcıya mevzuat metni ezberletmek yerine yapılacak işi önem sırasıyla göstermek.
Bu faz **salt okunurdur**; eğitim oluşturmaz, tamamlamaz, silmez veya tarihsel kayıtları değiştirmez.

## Gösterilen iki ayrı durum

1. **İşe Başlama Eğitimi**
   - Premium yaşam döngüsü geçişinden önce işe başlayan çalışanlarda `Tarihsel / takip dışı`.
   - Geçiş sonrası çalışanlarda `Eksik`, `Sonuç bekliyor`, `Tamamlandı`.
   - Geriye dönük yapay ihlal üretilmez.

2. **Temel İSG Eğitimi**
   - İlk eğitim için işe girişten itibaren üç aylık pencere.
   - `İlk temel eğitim bekliyor`, `Gecikmiş / eksik`, `Yakında yenilenecek`, `Geçerli`.

## “Bugün Ne Yapmalıyım?” öncelikleri

- İşe Başlama Eğitimi eksik
- Temel İSG gecikmiş / eksik
- Temel İSG yenilemesi yaklaşan
- İlk temel eğitim bekleyen
- Katılım / sonuç bekleyen eğitim
- Planlanmış yaklaşan eğitim

Kartlar yalnız mevcut Eğitim sekmelerine yönlendirir. **Hiçbir eğitim otomatik tamamlanmaz.**

## Feature flags

```text
TRAINING_PREMIUM_DASHBOARD_V1_ENABLED=true
TRAINING_PREMIUM_DASHBOARD_V1_FORCE_OFF=false
```

Dashboard ayrıca `TRAINING_PREMIUM_LIFECYCLE_V2_ENABLED=true` olmasını gerektirir.

## Rollback

İlk işlem:

```text
TRAINING_PREMIUM_DASHBOARD_V1_FORCE_OFF=true
```

Dashboard endpoint'i `enabled=false` döner ve frontend paneli tamamen kaldırır. Mevcut Eğitim ekranı aynen çalışmaya devam eder.

## Veri güvenliği

- Migration yoktur.
- DB yazma endpoint'i eklenmez.
- Eğitim, sınav, PDF, sertifika, katılım, sunum ve onay kayıtları değiştirilmez.
- İşe Başlama takibi tarihsel çalışanlara geriye dönük kırmızı ihlal üretmez.
- Dashboard API hatası mevcut Eğitim ekranını engellemez.

## Release kapıları

1. Backend read-only/policy testleri.
2. Frontend unit + ESLint.
3. Vite production build.
4. Chromium masaüstü kabul testi.
5. 390 px mobil taşma testi.
6. Staging özellik kapalı deploy.
7. Staging feature activation + health/log/DB karşılaştırma.
8. Production özellik kapalı deploy.
9. Production feature activation + health/log/DB karşılaştırma.

## Resmî mevzuat kaynağı

ÇSGB / İSGGM — Çalışanların İş Sağlığı ve Güvenliği Eğitimleri Sıkça Sorulan Sorular, 09.08.2026 kontrolü.
