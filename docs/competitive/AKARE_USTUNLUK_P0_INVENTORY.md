# P0-01 — Altın Akış Baseline Envanteri

**Referans:** `master`  
**Tarih:** 2026-08-23  
**Amaç:** Yeni geliştirmeye başlamadan önce çalışan akışların sınırlarını sabitlemek.  
**Kural:** Bu belge gözlem içerir; master üzerinde runtime değişikliği yapılmaz.

## 1. Uygulama giriş ve rol sınırı

| Alan | Mevcut gözlem | Koruma kararı |
|---|---|---|
| Frontend giriş | `frontend/src/main.jsx` | Menü ve route davranışı korunacak |
| Rol menüleri | `roleModules`, `mobilePrimaryByRole` | Mevcut rol listeleri değiştirilmeyecek |
| Mobil menü | Role göre en fazla dört öncelikli modül + menü | Yeni mobil katman bunun üzerine eklenecek |
| API prefix | Backend router'ları `/api/v1` altında | Mevcut endpoint sözleşmeleri korunacak |
| Tenant sınırı | OSGB/firma/işyeri erişim kontrolleri mevcut | Her yeni endpoint için negatif çapraz-firma testi şart |

## 2. Altın akışlar ve mevcut bağlar

| ID | Akış | Mevcut frontend | Mevcut backend | Riskli sınır |
|---|---|---|---|---|
| AF-01 | Saha ziyareti tamamlama | `field_offline.js`, `field_inspection.jsx` | `operations.py` | QR, GPS, imza, offline retry |
| AF-02 | Fotoğraflı saha tespiti | `field_inspection.jsx`, `field_inspection_offline.js` | `risks.py` ve ilgili saha/media uçları | Fotoğraf kuyruğu ve tekrar yükleme |
| AF-03 | Risk analizi | `risk.jsx` | `risks.py`, risk scoring servisleri | Skor yönteminin korunması |
| AF-04 | Ramak kala / olay / DÖF | `incidents.jsx` | `incidents.py` | Olay-DÖF ilişkisi ve raporlar |
| AF-05 | Eğitim yaşam döngüsü | `training.jsx`, `remote_basic_ohs_training.jsx` | `training*.py`, `remote_training.py` | Eski ve yeni eğitim kayıtlarının ayrılığı |
| AF-06 | KKD zimmet ve takip | `ppe.jsx` | `ppe.py` | Firma/personel erişimi ve durum geçişleri |
| AF-07 | Sağlık kayıtları | `health.jsx` | `health.py` | Hassas alan gizliliği ve rol matrisi |
| AF-08 | Doküman/acil durum/kurul/yıllık plan | İlgili mevcut sayfalar | İlgili mevcut router'lar | Dosya, onay ve arşiv geçmişi |
| AF-09 | OSGB ticari operasyonu | `osgb.jsx`, `customer_360.jsx` | `operations.py`, OSGB router'ları | OSGB/firma kapsamının karışmaması |
| AF-10 | PWA ve mobil başlatma | `main.jsx`, mevcut PWA altyapısı | Sağlık ve auth uçları | Açılış, session ve offline geri dönüşü |

## 3. Mevcut offline davranışı

### Ziyaret tamamlama kuyruğu

Kaynak: `frontend/src/field_offline.js`

- Kuyruk anahtarı: `isg_field_offline_queue_v1`
- Üst sınır: 40 kayıt
- Yaş sınırı: 7 gün
- Yeniden deneme: 5 deneme
- Kapsam: kullanıcı ve OSGB ile filtreleme
- Gönderim: `PATCH /api/v1/operations/visits/{visit_id}/complete`
- Gönderilen alanlar: GPS, doğrulama kodu, imza
- Local storage kotasında imza küçültülüyor/çıkarılıyor

**P0 kontrolü:** Beş deneme sonrası kaydın kullanıcıya görünür bir kurtarma
durumu olmadan kuyruktan düşmediği kanıtlanmalı. Mevcut davranış değiştirilmeden
önce adapter ve görünür dead-letter/retry tasarımı hazırlanmalı.

### Fotoğraflı saha tespit kuyruğu

Kaynak: `frontend/src/field_inspection_offline.js`

- Kuyruk anahtarı: `isg_field_finding_queue_v1`
- Üst sınır: 30 kayıt
- Yaş sınırı: 14 gün
- Yeniden deneme: 8 deneme
- Fotoğraf sınırı: kayıt başına 5
- Toplam data URL sınırı: 7.000.000 karakter
- Kapsam: kullanıcı, OSGB ve firma
- Zincir: saha tespiti → risk → DÖF → medya senkronizasyonu
- Local storage kotasında kuyruk küçültme fallback'i var

**P0 kontrolü:** Fotoğraf yüklemesi yarıda kaldığında metin/risk/DÖF kaydının
durumu ve kalan fotoğrafların tekrar gönderilebilirliği gerçek cihaz testinde
kanıtlanmalı.

## 4. Mevcut güvenlik ve uyumluluk sınırları

- `operations.py` saha tamamlamasında işyeri QR doğrulaması uyguluyor.
- GPS ve imza biçimi/boyutu backend'de doğrulanıyor.
- `ppe.py` firma erişimi ve personelin firmaya ait olma kontrolünü yapıyor.
- `remote_training.py` ayrı feature/table yaşam döngüsüyle additive tasarlanmış.
- Backend startup ve CI PostgreSQL migration/parity kontrolleri mevcut.
- Frontend CI test, lint, build, Playwright E2E ve audit adımlarını çalıştırıyor.

## 5. P0 regresyon matrisi

Her yeni commit için aşağıdaki kombinasyonlar çalıştırılacak:

| Boyut | Zorunlu değerler |
|---|---|
| Flag | Kapalı legacy / açık yeni |
| Görünüm | 390x844 / 430x932 / tablet / masaüstü |
| Ağ | Çevrimiçi / çevrimdışı / bağlantı geri geldi |
| Rol | Global yönetici / OSGB yöneticisi / uzman / hekim / DSP / salt okunur |
| Tenant | Aynı firma / başka firma / başka OSGB |
| Veri | Eski kayıt / yeni kayıt / boş liste / hata yanıtı |
| Geri dönüş | Retry / sayfa yenileme / session yenileme / rollback |

## 6. Tamamlanan güvenli kod işi

**MOB-P0-01 — Sync durum adapter'ı**

Sınırları:

- Mevcut offline queue formatlarını okumaya devam edecek.
- Mevcut API endpoint'lerini değiştirmeyecek.
- Sadece görünür durum ve güvenli retry katmanı ekleyecek.
- Başarılı, bekliyor, tekrar deneniyor, kalıcı hata durumlarını ayıracak.
- Yeni davranış feature flag kapalıyken hiç çalışmayacak.
- Unit test + mevcut saha E2E + gerçek cihaz smoke olmadan yayınlanmayacak.

Bu adapter tamamlandı; mevcut offline kuyruklarının doğrudan yeniden yazılması
yine yasaktır.

## 7. Sıradaki güvenli kod işi

**ESS-P0-01 — Çalışan Panelim salt okunur self-servis özeti**

- Backend ve frontend bayrakları varsayılan olarak kapalıdır.
- Yeni `/api/v1/self-service/me` ucu yalnızca `read_only` rolünü kabul eder.
- Açık kullanıcı→çalışan eşleştirmesi, firma ve OSGB bağı tekrar doğrulanır.
- Eğitim, KKD, bildirim ve yalnız tarih seviyesinde sağlık özeti sunulur.
- Mevcut İBYS ve MEDULA/e-Reçete akışlarına dokunulmaz.
- Global yönetici ve OSGB saha menü matrisi değiştirilmez.
- Flag kapalı legacy smoke, çapraz tenant/rol negatif testleri, gerçek cihaz
  smoke ve kill-switch kontrolü olmadan canary açılmaz.
