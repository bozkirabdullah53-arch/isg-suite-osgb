# Faz 6 — Sunum Onayı, E-İmza Uyumu ve Tarihsel Koruma

Bağlı epic: #74  
Görev: #80

## Amaç

Üretilmiş NACE eğitim sunumunu manifest, PPTX ve PDF hash'leriyle birlikte onaylamak; onay kaydını değişmez bir denetim izi olarak korumak ve mevcut e-imza orkestrasyonuyla çakışmadan çalışmak.

Bu faz mevcut eğitim, sınav, puanlama, sertifika, eğitim PDF veya e-imza tablolarını yeniden yazmaz.

## Ayrı onay tablosu

Yeni tablo:

`training_presentation_approvals`

Her sunum sürümü için en fazla bir onay kaydı bulunur.

Benzersiz alanlar:

- `presentation_version_id`
- `event_hash`

Onay tablosu şirket bazlı PostgreSQL RLS ve FORCE RLS kullanır.

## Dondurulan bilgiler

Onay anında aşağıdaki değerler ayrı onay kaydına kopyalanır:

- sunum sürüm ID'si
- eğitim, şirket ve şube kimliği
- onay yöntemi
- manifest SHA-256
- PPTX SHA-256
- PDF SHA-256
- onaylayan kullanıcı ID'si
- onaylayan ad/soyad snapshot'ı
- onaylayan rol snapshot'ı
- isteğe bağlı onay notu
- varsa e-imza talep ve sertifika kanıtları
- hukuki açıklama
- onay event hash'i
- onay zamanı

Onay kaydı ORM seviyesinde güncellenemez ve silinemez.

## Onay yöntemleri

### 1. Uygulama içi uzman onayı

Kod:

`application_approval`

Bu yöntem sunumun uzman tarafından incelendiğini ve hash'lerin onay anında kilitlendiğini gösterir.

Her kayıtta aşağıdaki hukuki uyarı bulunur:

> Bu kayıt uygulama içi uzman onayıdır; 5070 sayılı Kanun kapsamında nitelikli elektronik imza yerine geçmez.

Uygulama onayında e-imza talebi kabul edilmez.

### 2. Doğrulanmış nitelikli e-imza onayı

Kod:

`qualified_esign`

Yeni bir e-imza sistemi oluşturulmaz. Mevcut `ESignatureRequest` orkestrasyonu kullanılır.

Onay için bütün koşullar zorunludur:

- e-imza talebi aynı şirkete ait olmalıdır
- talep aktif olmalıdır
- talep durumu `verified` olmalıdır
- doğrulama durumu `verified` olmalıdır
- format PAdES olmalıdır
- kilitli `document_sha256`, sunum PDF hash'iyle birebir eşleşmelidir
- imzalı belge hash'i bulunmalıdır
- sertifika nitelikli olarak doğrulanmış olmalıdır
- iptal/geçerlilik kontrolü `good`, `valid` veya `ok` olmalıdır

Bu şartlardan biri sağlanmazsa sunum onaylanmaz. Eğitim, sınav, sertifika veya mevcut e-imza kaydı değişmez.

## Onay ön koşulları

- Feature flag açık olmalıdır.
- Rol `global_admin`, `company_admin` veya `safety_specialist` olmalıdır.
- Sunum sürümü `generated` olmalıdır.
- Manifest, PPTX ve PDF hash'leri tam 64 karakter olmalıdır.
- PPTX ve PDF storage key kayıtları bulunmalıdır.
- Kullanıcının teyit ettiği manifest hash'i sürüm hash'iyle eşleşmelidir.
- Aynı sürüm için önceki onay kaydı bulunmamalıdır.

## Onaylı sürüm kilidi

Onaydan sonra aşağıdaki alanlar değiştirilemez:

- manifest ve bütün kaynak snapshot alanları
- PPTX/PDF storage key
- PPTX/PDF SHA-256
- dosya boyutları
- MIME türleri
- üretim zamanı
- onaylayan kullanıcı ve onay zamanı

Onaylı sürüm:

- yeniden render edilemez
- `failed`, `draft` veya `generated` durumuna döndürülemez
- yalnız `archived` olabilir

Arşivlenmiş sürüm tekrar başka duruma geçirilemez.

Yeni içerik veya yeni dosya gerekiyorsa yeni sunum sürümü oluşturulur ve yeni onay gerekir.

## Arşivleme

Yalnız değişmez onay kaydı bulunan `approved` sürüm arşivlenebilir.

Arşivleme:

- dosyaları silmez
- hash'leri değiştirmez
- onay kaydını değiştirmez
- tarihsel indirmeyi engellemez
- yalnız sürüm durumunu `archived` yapar ve arşiv zamanını kaydeder

## API

Salt okunur onay:

- `GET /api/v1/trainings/{training_id}/presentation-versions/{version_id}/approval`

Onay:

- `POST /api/v1/trainings/{training_id}/presentation-versions/{version_id}/approve`

Arşivleme:

- `POST /api/v1/trainings/{training_id}/presentation-versions/{version_id}/archive`

Onay isteği örneği:

```json
{
  "approval_method": "application_approval",
  "confirmed_manifest_hash": "64-karakter-sha256",
  "approval_note": "Sunum ve kaynaklar incelendi."
}
```

Nitelikli e-imza yöntemi için ayrıca `esign_request_id` gönderilir.

## Hata izolasyonu

Onay veya e-imza hatasında:

- veritabanı işlemi rollback edilir
- sunum sürümü eski durumunda kalır
- PPTX/PDF dosyaları silinmez
- eğitim durumu değişmez
- sınav ve puanlama değişmez
- sertifika ve katılım PDF'leri etkilenmez
- hata yalnız sunum onay yanıtında gösterilir

## Migration ve rollback

Revision:

`0080_training_presentation_approvals`

Parent:

`0079_training_presentation`

Upgrade yalnız onay tablosu, indeksler, kısıtlar ve RLS politikasını ekler.

Downgrade zinciri CI'da aşağıdaki şekilde doğrulanır:

1. `head` — sürüm ve onay tabloları bulunur
2. `0080 → 0079` — yalnız onay tablosu kalkar; sunum sürümleri ve çekirdek eğitim tabloları kalır
3. `0079 → 0078` — yalnız sunum sürüm tablosu kalkar; eğitim, NACE ve sınav tabloları kalır
4. yeniden `head` — parity ve RLS tekrar doğrulanır

## Production geçişi

Faz 6 deployunda feature flag kapalı kalır. Migration boş onay tablosu oluşturur. Production kullanıcısı onay veya arşivleme işlemi başlatamaz. Kontrollü açılış ve kullanıcı kabulü Faz 7 kapsamındadır.
