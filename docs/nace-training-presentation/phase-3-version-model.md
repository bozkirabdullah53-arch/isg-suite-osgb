# Faz 3 — Sürümlemeli NACE Eğitim Sunumu Veri Modeli

Bağlı epic: #74  
Görev: #77

## Amaç

Sunum üretiminden önce her içerik manifestini ve kullanılan NACE kaynaklarını ayrı, denetlenebilir ve değişmez bir sürüm olarak saklamak.

## İzole tablo

Yeni tablo:

`training_presentation_versions`

Mevcut aşağıdaki tablolara kolon veya davranış eklenmez:

- `training_sessions`
- `training_nace_snapshots`
- `training_exam_snapshots`
- `training_exam_snapshot_items`
- `training_participants`
- sertifika, PDF ve imza tabloları

Migration mevcut kayıtlara backfill yapmaz. Production'da tablo boş oluşturulur.

## Sürüm kimliği

Her eğitim için sürüm numarası 1'den başlar ve artar.

Benzersiz kısıt:

`(training_id, version)`

Aynı eğitim için farklı sürümler korunabilir. Aynı sürüm numarası ikinci kez kullanılamaz.

## Durumlar

- `draft`: manifest ve kaynak snapshot donduruldu, dosya üretilmedi
- `generated`: PPTX/PDF üretimi tamamlandı
- `approved`: yetkili onayı tamamlandı
- `failed`: yalnız sunum üretim hattı başarısız oldu
- `archived`: geçmiş sürüm salt okunur arşive alındı

Bu durumlar mevcut eğitim durumlarından tamamen ayrıdır. Sunumun `failed` olması eğitimi iptal veya başarısız yapmaz.

## Değişmez kaynak alanları

Aşağıdaki alanlar sürüm oluşturulduktan sonra yerinde değiştirilemez:

- eğitim, şirket, şube ve NACE snapshot bağlantıları
- sürüm numarası
- sözleşme/şablon/manifest sürümleri ve hash'leri
- tam manifest JSON'u
- NACE kodu, açıklaması, tehlike sınıfı ve içerik profili
- katalog sürümü ve hash'i
- kaynak snapshot JSON'u
- beş eğitim konusu
- teknik ve özel riskler
- çıktı biçimleri
- oluşturan kullanıcı ve oluşturma zamanı

Bu alanlardan biri değişecekse yeni sunum sürümü oluşturulur. ORM `before_update` koruması değişikliği reddeder.

## Güncellenebilir yaşam döngüsü alanları

İleriki fazlarda yalnız aşağıdaki alanlar güncellenebilir:

- durum
- PPTX/PDF storage key, dosya hash'i, boyut ve MIME
- üretim zamanı
- hata kodu/açıklaması
- onaylayan ve onay zamanı
- arşiv zamanı

## API davranışı

Salt okunur tarihçe:

- `GET /api/v1/trainings/{training_id}/presentation-versions`
- `GET /api/v1/trainings/{training_id}/presentation-versions/{version_id}`

Yeni taslak:

- `POST /api/v1/trainings/{training_id}/presentation-versions`

POST yalnız düzenleme yetkisi olan roller için ve `NACE_TRAINING_PRESENTATION_ENABLED=true` olduğunda çalışır. Feature flag kapalıysa veritabanı sorgusu/yazması başlamadan güvenli 409 döner.

GET tarihçe uçları feature flag kapalı olsa da ileride oluşturulmuş tarihsel kanıtları okumaya devam eder.

## Depolama ve renderer sınırı

Faz 3:

- PPTX üretmez
- PDF üretmez
- object storage çağırmaz
- storage key yazmaz
- mevcut eğitim çıktısını değiştirmez

Dosya üretimi ve doğrulanmış object storage yazması Faz 4 (#78) kapsamındadır.

## Tenant güvenliği

- API mevcut `ensure_company_access` sınırını kullanır.
- PostgreSQL RLS ve FORCE RLS aktiftir.
- Şirket kapsamı dışında listeleme, detay veya taslak oluşturma yapılamaz.

## Migration ve rollback

Revision:

`0079_training_presentation`

Parent:

`0078_training_nace`

Upgrade yalnız yeni tabloyu, indeksleri, kısıtları ve RLS politikasını ekler.

Downgrade yalnız `training_presentation_versions` tablosunu kaldırır. Eğitim, NACE, sınav, PDF ve sertifika tablolarına dokunmaz.

CI aşağıdaki turu çalıştırır:

1. `alembic upgrade head`
2. şema/RLS/benzersiz kısıt doğrulaması
3. `alembic downgrade 0078_training_nace`
4. yalnız sunum tablosunun kalktığının doğrulanması
5. `alembic upgrade head`
6. parity doğrulamasının tekrarı

## Production geçişi

İlk deployda feature flag kapalı kalır. Migration yalnız boş tablo oluşturur. Yeni taslak üretimi kullanıcıya açılmaz. Böylece mevcut eğitim, sınav, PDF ve sertifika iş akışları aynı davranışı sürdürür.
