# Dijital Personel Kartı — Faz 3 Profil Çekirdek Modeli

## Durum

- Feature varsayılan kapalıdır.
- Production aktivasyonu bu fazın kapsamında değildir.
- Mevcut `employees`, `isg_professionals`, `users` ve `workplace_assignments` tabloları değiştirilmez.
- Tarihsel kayıtlara backfill uygulanmaz.
- Dosya, fotoğraf, CV, dış paylaşım ve restricted veri bu fazda yoktur.

## Yeni tablolar

### `personnel_profiles`

Mevcut bir özneyi yeni profil uzantısına açıkça bağlayan kök tablodur.

Bir kayıt yalnız şu iki biçimden biri olabilir:

1. `subject_type=employee`, `employee_id` dolu, `professional_id` boş
2. `subject_type=professional`, `professional_id` dolu, `employee_id` boş

Aynı şirket ve aynı özne için ikinci profil oluşturulamaz.

Tenant alanları:

- `osgb_id`
- `company_id`
- `branch_id`

Özne ve tenant bağlantıları yerinde değiştirilemez. Profil yalnız `active → archived` geçişi yapabilir; arşivlenmiş profil tekrar aktif edilemez.

### `personnel_profile_contacts`

Yalnız aşağıdaki normal iletişim türlerini destekler:

- kurumsal e-posta
- alternatif e-posta
- iş telefonu
- cep telefonu

Ev adresi ve acil kişi bilgisi bu tabloda yoktur.

Her değişiklik yeni `(entry_key, version)` satırıdır. Önceki satır güncellenmez.

### `personnel_profile_competencies`

Uygulama login rolünden ayrı mesleki görev/yeterlilik/uzmanlık kayıtlarını tutar.

Kategoriler:

- professional duty
- certificate based
- technical specialization
- training authority
- other

İstemci bu fazda kaydı `verified` yapamaz; yeni sürüm `unverified` başlar.

### `personnel_profile_experiences`

Gizli müşteri dokümanı taşımayan profesyonel deneyim özetini tutar.

Tam proje/doküman içeriği yoktur. Dış paylaşım bu fazda kapalıdır.

## Bilerek eklenmeyen alanlar

- TCKN
- ev adresi
- acil kişi/telefon
- sağlık verisi veya teşhis
- adli sicil/mahkûmiyet
- engellilik teşhisi
- maaş
- disiplin bilgisi
- belge dosyası veya object key
- CV dosyası
- paylaşım alıcısı veya linki

Pydantic şemaları `extra=forbid` kullanır; tanımsız/restricted alanlar sessizce saklanmaz.

## Yetkilendirme

### Yazma ve arşivleme

Yalnız:

- global admin
- company admin

Ayrıca her işlemde mevcut `ensure_company_access` kontrolü uygulanır.

### Genişletilmiş profil okuma

- global admin: yetkili kapsam
- company admin: yetkili şirket/OSGB kapsamı
- uzman/hekim/DSP: yalnız açıkça kendi `IsgProfessional` kaydına bağlı profil
- saha rolü: işyeri çalışanlarının genişletilmiş iletişim/deneyim verisini okuyamaz
- müşteri/salt okunur kullanıcı: tam profil erişimi yok

### Profesyonel profil başlatma

Seçili şirkette aktif `WorkplaceAssignment` bulunması zorunludur.

## Sürümleme

İletişim, yeterlilik ve deneyim satırları değişmezdir.

- Yeni kayıt: sistem UUID `entry_key`, sürüm 1
- Güncelleme: mevcut `entry_key`, zorunlu değişiklik nedeni, sürüm N+1
- `supersedes_id`: önceki sürüme bağlanır
- Aynı içerik tekrar gönderilirse yeni sürüm oluşturulmaz
- Snapshot yalnız her `entry_key` için en yüksek sürümü gösterir
- Tarihsel satırlar silinmez veya güncellenmez

## Veritabanı güvenliği

Dört tablonun tamamı `company_id` taşır.

PostgreSQL’de:

- RLS etkin
- FORCE RLS etkin
- `app.allowed_company_ids` tenant kapsamı
- migration/system bağlamı için mevcut kontrollü unset/bypass davranışı

## Migration

- Revision: `0081_personnel_profile_core`
- Down revision: `0080_presentation_approvals`

Upgrade yalnız dört yeni tablo ve bunların index/kısıt/RLS politikalarını ekler.

Downgrade yalnız şu tabloları kaldırır:

- `personnel_profile_experiences`
- `personnel_profile_competencies`
- `personnel_profile_contacts`
- `personnel_profiles`

Korunan tablolar:

- employees
- isg_professionals
- users
- workplace_assignments
- training
- exam
- certificate
- committee
- risk
- health
- document
- approval/signature

## Normal rollback

Production’da normal rollback veritabanı downgrade değildir:

1. `PERSONNEL_PROFILE_CARD_FORCE_OFF=true`
2. Gerekirse `PERSONNEL_PROFILE_CARD_ENABLED=false`
3. Pilot allowlist boşaltılır

Profil tabloları ve tarihsel sürümler yerinde kalır. Eski personel ve profesyonel ekranları çalışmaya devam eder.

## Sonraki faz

Faz 4 private object storage, fotoğraf, CV ve normal mesleki belge sürümleme altyapısıdır. R2 durability ve kategori retention readiness tamamlanmadan production dosya yüklemesi açılmaz.
