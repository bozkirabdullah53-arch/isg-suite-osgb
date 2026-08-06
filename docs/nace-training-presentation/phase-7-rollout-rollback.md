# Faz 7 — Kontrollü Pilot, Görsel QA ve Rollback Runbook

## 1. Güvenli varsayılan

Production ortamında aşağıdaki değerler varsayılan olarak korunur:

```env
NACE_TRAINING_PRESENTATION_ENABLED=false
NACE_TRAINING_PRESENTATION_FORCE_OFF=false
NACE_TRAINING_PRESENTATION_PILOT_COMPANY_IDS=
```

Bu durumda:

- Sunum paneli hiçbir şirkete görünmez.
- Manifest önizleme, taslak, render, onay ve arşiv yazma işlemleri çalışmaz.
- Mevcut eğitim, 20 soruluk sınav, katılım PDF'leri ve sertifikalar çalışmaya devam eder.
- Daha önce oluşturulmuş tarihsel sunum sürümleri, onay kayıtları ve hash doğrulamalı indirmeler korunur.
- Boş pilot allowlist güvenli biçimde **hiçbir şirkete izin vermez**.

## 2. Üçlü erişim kapısı

Yeni yazma veya önizleme işlemi için üç koşulun tamamı zorunludur:

1. `NACE_TRAINING_PRESENTATION_ENABLED=true`
2. `NACE_TRAINING_PRESENTATION_FORCE_OFF=false`
3. Eğitim kaydının `company_id` değeri `NACE_TRAINING_PRESENTATION_PILOT_COMPANY_IDS` içinde bulunmalıdır.

`FORCE_OFF=true` diğer bütün ayarlardan önceliklidir.

Allowlist virgülle ayrılmış pozitif şirket kimliklerinden oluşur:

```env
NACE_TRAINING_PRESENTATION_PILOT_COMPANY_IDS=35
```

Birden fazla şirket ancak ayrı bir kabul kararıyla eklenir:

```env
NACE_TRAINING_PRESENTATION_PILOT_COMPANY_IDS=35,99
```

Allowlist içeriği API yanıtlarında yayımlanmaz. API yalnız mevcut eğitim şirketinin pilot olup olmadığına ilişkin boolean durum bilgisi döndürür.

## 3. Kontrollü pilot aktivasyon sırası

Genel aktivasyon yapılmaz. Pilot açılış sırası değiştirilemez:

1. Production commit, CI ve deploy sağlık durumu doğrulanır.
2. Object storage erişimi ve hash doğrulamalı tarihsel indirme kontrol edilir.
3. Yalnız bilinen **tek bir test şirketi** belirlenir.
4. `NACE_TRAINING_PRESENTATION_PILOT_COMPANY_IDS=<TEST_COMPANY_ID>` ayarlanır.
5. `NACE_TRAINING_PRESENTATION_FORCE_OFF=false` doğrulanır.
6. En son `NACE_TRAINING_PRESENTATION_ENABLED=true` yapılır.
7. Gerçek resmi kayıt yerine `[TEST]` başlıklı eğitim kullanılır.
8. Kullanıcı kabulü tamamlanana kadar başka şirket eklenmez.

Test şirketi kimliği kesin olarak doğrulanmadan allowlist ayarı yapılmaz. Pilot genişletmesi için ilk pilot kullanıcının açık kabulü alınmalıdır.

## 4. Pilot kabul senaryosu

### 4.1 Mevcut akış regresyonu

- Eğitim kaydı oluşturma ve görüntüleme
- Katılımcı seçimi
- NACE sınıflandırması
- 5 temel + 15 işe özgü sınav
- Katılım PDF'leri
- Sertifika PDF'si
- Sayfa yenilemeden firma/personel/form bağlamının korunması

### 4.2 Sunum akışı

1. Hazırlık kontrollerinin tamamı yeşil görünür.
2. İçerik önizlemesi açılır; hiçbir kayıt veya dosya oluşturmaz.
3. Sunum taslak sürümü oluşturulur.
4. PPTX ve PDF aynı manifestten üretilir.
5. Her iki dosya indirilir ve açılır.
6. Dosya hash'leri kayıtlarla eşleşir.
7. Uygulama içi uzman onayı seçilirse “nitelikli elektronik imza değildir” uyarısı görünür.
8. PAdES seçilirse doğrulanmış e-imza talep numarası zorunlu olur.
9. Onay sonrasında manifest, PPTX ve PDF hash'leri değişmez kalır.
10. Onaylı sürüm yalnız arşivlenebilir; yeni içerik için yeni sürüm oluşturulur.

### 4.3 Görsel QA matrisi

Aşağıdaki viewport'larda yatay taşma, üst üste binme ve erişilemeyen kontrol olmamalıdır:

| Ekran | Boyut |
|---|---:|
| Masaüstü | 1440 × 900 |
| Laptop | 1024 × 768 |
| Tablet | 768 × 1024 |
| Mobil | 390 × 844 |

Kontroller:

- Düğme yüksekliği en az 44 px
- Modal ekran dışına taşmaz
- Uzun hash metinleri yatay kaydırma oluşturmaz
- Klavye odağı modal kapanınca eski düğmeye döner
- ESC ile modal kapanır
- Ekran okuyucu başlık ve `role=dialog` tanımları korunur

## 5. Acil rollback

Bir hata, gecikme, storage sorunu, yanlış içerik veya kullanıcı etkisi görülürse ilk müdahale:

```env
NACE_TRAINING_PRESENTATION_FORCE_OFF=true
```

Bu değişiklik:

- Paneli ve bütün yeni yazma/önizleme işlemlerini kapatır.
- Eğitim, sınav, PDF ve sertifika akışlarını açık bırakır.
- Tarihsel sunum sürümlerini, onay kayıtlarını ve dosya indirmelerini silmez.
- Veritabanı downgrade gerektirmez.

İkinci güvenlik adımı:

```env
NACE_TRAINING_PRESENTATION_ENABLED=false
NACE_TRAINING_PRESENTATION_PILOT_COMPANY_IDS=
```

## 6. Kod rollback

Force-off yeterli olmazsa:

1. Son doğrulanmış önceki production commit yeniden deploy edilir.
2. Veritabanı tabloları normal rollback sırasında silinmez.
3. Object storage dosyaları otomatik toplu silinmez.
4. Tarihsel sürüm ve onay kayıtları salt okunur korunur.
5. Sorunun yeniden üretimi için ilgili eğitim ID'si, sunum sürüm ID'si, manifest hash'i ve deploy commit'i kaydedilir.

Destructive Alembic downgrade yalnız ayrı bakım penceresinde, doğrulanmış yedek ve açık yönetici kararıyla yapılabilir. Normal özellik rollback yöntemi değildir.

## 7. Pilot genişletme kriteri

İkinci şirkete geçiş için aşağıdaki şartların tamamı gerekir:

- Ana CI başarılı
- Rollout CI başarılı
- PostgreSQL migration/parity başarılı
- Dört ekranlı E2E başarılı
- PPTX/PDF açılma ve hash doğrulaması başarılı
- Uygulama onayı ve PAdES hata senaryoları başarılı
- Force-off testi başarılı
- ilk pilot kullanıcının açık kabulü alınmış
- Eğitim/sınav/PDF/sertifika regresyonu bulunmamış

Bu kriterler tamamlanmadan genel aktivasyon veya allowlist genişletmesi yapılmaz.
