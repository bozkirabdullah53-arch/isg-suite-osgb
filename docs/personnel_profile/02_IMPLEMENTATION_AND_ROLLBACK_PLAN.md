# Dijital Personel Kartı — Uygulama, Test ve Rollback Planı

**Plan ilkesi:** Her faz küçük, izole, geriye uyumlu, ayrı PR ile ve kapalı feature flag altında geliştirilecektir.

## Değişmez koruma listesi

Aşağıdaki çalışan akışlar her fazda regresyon kapısıdır:

- Personel listesi
- Tekli personel ekleme
- Personel Excel şablonu
- Personel Excel içe aktarma
- Personel Excel dışa aktarma
- Tekli/toplu güvenli pasife alma
- İSG profesyoneli oluşturma ve kullanıcı hesabı bağlama
- Profesyonel askıya alma/aktifleştirme
- Profesyonel görevlendirmeleri
- Eğitim ve 20 soruluk sınav
- Katılım ve başarı belgeleri
- İSG Kurulu
- Risk analizi ve DÖF
- Sağlık modülü veri ayrımı
- Mevcut PDF servisleri
- Belge onay ve e-imza
- Bildirimler
- Object storage local/dual/R2 davranışı
- Şirket, işyeri, OSGB ve rol izolasyonu
- Masaüstü, tablet ve mobil düzen

## Faz 1 — Envanter, karar kayıtları ve güvenli kabuk

### Amaç

Kod yazmadan önce gerçek mimariyi ve veri sınıflandırmasını sabitlemek.

### Teslimatlar

- Mevcut sistem analiz raporu
- Veri sınıflandırma matrisi taslağı
- Yetki matrisi taslağı
- Hukuki/organizasyonel readiness checklist taslağı
- GitHub epic ve alt görevler
- Önerilen feature flag sözleşmesi
- Etki ve rollback matrisi

### Kod etkisi

Yok.

### Kabul

- Mevcut sistem alanları ve API’leri uydurulmadan belgelenmiş olmalı.
- TCKN ve `special_status` riskleri kayıt altına alınmış olmalı.
- Restricted veri geliştirmesi varsayılan kapalı olmalı.

## Faz 2 — Kapalı feature flag ve salt okunur profil özeti

### Amaç

Migration yapmadan, mevcut `Employee` ve `IsgProfessional` kayıtlarından güvenli minimum özet üretmek.

### Önerilen ayarlar

```text
PERSONNEL_PROFILE_CARD_ENABLED=false
PERSONNEL_PROFILE_CARD_FORCE_OFF=false
PERSONNEL_PROFILE_CARD_PILOT_COMPANY_IDS=
```

### API

Eklemeli yollar:

- `GET /api/v1/personnel-profiles/readiness`
- `GET /api/v1/personnel-profiles/employee/{employee_id}/summary`
- `GET /api/v1/personnel-profiles/professional/{professional_id}/summary`

### Güvenlik

- Mevcut şirket/OSGB erişim yardımcıları kullanılır.
- TCKN ham değer dönülmez.
- `special_status` varsayılan özet yanıtından çıkarılır.
- Sağlık ayrıntısı ve restricted veri yoktur.

### Frontend

- Mevcut listeler değiştirilmez.
- Flag açık ve pilot şirket uygunsa “Kartı Aç” eylemi eklenir.
- Hata olursa eski ekran çalışmaya devam eder.

### Rollback

- `PERSONNEL_PROFILE_CARD_FORCE_OFF=true`
- Migration yoktur.

## Faz 3 — İzole profil öznesi ve sıradan profesyonel bilgiler

### Amaç

Mevcut tablolara dokunmadan profil uzantısı oluşturmak.

### Yeni tablolar

- `personnel_profiles`
- `personnel_profile_contacts`
- `personnel_profile_competencies`
- `personnel_profile_experiences`

### Kurallar

- Otomatik merge yok.
- Bir profil açıkça bir `Employee` veya `IsgProfessional` kaydına bağlanır.
- Kullanıcı ilişkisi opsiyonel ve doğrulanmış olmalıdır.
- Tenant kolonları ve PostgreSQL RLS eklenir.
- Eski kayıtlara backfill yapılmaz.

### Rollback

- Flag kapatma normal rollback’tir.
- Migration downgrade yalnız yeni tabloları kaldırır.
- Mevcut personel/profesyonel tabloları değişmez.

## Faz 4 — Fotoğraf, CV ve sıradan belge sürümleme

### Amaç

Private object storage üzerinde sürümlemeli dosya yönetimi.

### Yeni tablolar

- `personnel_profile_documents`
- `personnel_profile_document_versions`
- `personnel_profile_file_events`

### İlk açılacak belge sınıfları

- profil fotoğrafı
- mevcut CV
- diploma
- uzman/hekim/DSP mesleki belge
- eğitici belgesi
- ilk yardımcı belgesi
- MYK ve operatör belgeleri
- diğer sıradan mesleki yeterlilikler

### Açılmayacak belge sınıfları

- adli sicil
- ayrıntılı sağlık raporu
- biyometrik şablon
- disiplin belgesi
- maaş belgesi

### Storage

- Yalnız mevcut object-store adapter
- Private-by-default
- Hassas bilgi içermeyen object key
- SHA-256 checksum
- boyut/MIME/magic-byte/AV kontrolü
- atomik DB + object-store davranışı
- yeni sürüm eskisini ezmez

### Rollback

- Yeni yükleme flag ile kapatılır.
- Tarihsel dosya ve meta kayıtları silinmez.
- Başarısız yüklemede geçerli kayıt bırakılmaz.

## Faz 5 — Yeterlilik, belge durumu ve süre takibi

### Amaç

Mesleki görev ve uygulama rolünü birbirinden ayırmak; belge durumlarını hesaplamak.

### Durumlar

- valid
- expiring_soon
- expired
- awaiting_verification
- verified
- rejected
- missing
- archived
- revoked

### Kurallar

- Renk tek başına durum taşımaz.
- Metin, ikon ve erişilebilir etiket birlikte kullanılır.
- Geçerlilik için tarih ve doğrulama kuralları zorunludur.
- “Süresiz” seçeneği ayrı tutulur.
- Kullanıcı keyfi olarak “geçerli” işaretleyemez.

## Faz 6 — Profesyonel PDF CV

### Amaç

Onaylı ve alan düzeyinde seçilmiş veriden sürümlemeli A4 PDF üretmek.

### Akış

1. Alan önizlemesi
2. Kullanıcı seçimi
3. Restricted-data dışlama kontrolü
4. Manifest dondurma
5. PDF üretimi
6. PDF doğrulama
7. Private storage
8. Hash ve sürüm kaydı
9. Audit

### Otomatik dışlanacak alanlar

- tam TCKN
- tam doğum tarihi (zorunlu değilse)
- ev adresi
- acil kişi
- sağlık ayrıntısı
- adli sicil
- maaş
- disiplin
- restricted belge
- iç audit notu

### Rollback

- CV üretim flag’i kapatılır.
- Eski yüklenmiş CV sürümleri okunabilir kalır.

## Faz 7 — Kontrollü paylaşım paketi

### Amaç

Müşteri şirkete tam kart erişimi vermeden, amaç ve süre ile sınırlandırılmış paket oluşturmak.

### Ön koşullar

- alıcı kimliği
- alıcı kuruluşu
- paylaşım amacı
- hukuki aktarım şartı
- seçili alanlar
- seçili belgeler
- son kullanma tarihi
- yetkilendiren kullanıcı
- personel bildirim/onay durumu

### Güvenlik

- Restricted belgeler varsayılan seçili değildir.
- Kalıcı public URL yoktur.
- Tek kullanımlık veya kısa süreli erişim vardır.
- Link iptali desteklenir.
- Her görüntüleme ve indirme auditlenir.

### Rollback

- `PERSONNEL_PROFILE_EXTERNAL_SHARING_ENABLED=false`
- Aktif linkler iptal edilir.
- Tarihsel paylaşım audit kayıtları korunur.

## Faz 8 — Restricted veri için hukuk kapısı

### Amaç

Teknik altyapı olsa bile hukuki ve organizasyonel yapılandırma tamamlanmadan özel nitelikli veri işlememek.

### Varsayılan

```text
PERSONNEL_PROFILE_RESTRICTED_DATA_ENABLED=false
```

### Zorunlu readiness

Her restricted kategori için:

- amaç
- hukuki işleme şartı
- veri sahibi kategorisi
- yetkili roller
- alıcılar
- saklama süresi
- imha yöntemi
- paylaşım yasağı/koşulu
- audit seviyesi
- organizasyonel politika

### Sağlık

- Ayrıntılı sağlık verisi mevcut sağlık modülünde kalır.
- Personel kartı yalnız gerekli uygunluk durumunu gösterebilir.
- Uzman, normal admin, müşteri ve yetkisiz İK ayrıntıya erişemez.

### Adli sicil

- Hukuki assessment yoksa upload alanı bile gösterilmez.
- Eksik belge sayılmaz.
- CV veya normal pakete hiçbir zaman otomatik girmez.

## Faz 9 — Bildirim, retention ve veri sahibi talepleri

### Bildirimler

- 90/60/30/15/7 gün
- süresi doldu
- belge adı yerine minimum gerekli bildirim metni
- rol ve kapsam kontrollü alıcılar
- mükerrer bildirim koruması

### Retention

Her kategori için ayrı kural:

- aktif saklama
- arşiv
- imha uygunluğu
- yasal blok
- paylaşım paketi ve türetilmiş PDF temizliği
- R2 ve DB eşgüdümü

### Veri sahibi akışları

- görme
- düzeltme
- tamamlama
- paylaşım geçmişi
- hukuken uygunsa silme/imha talebi

## Faz 10 — Tam regresyon, pilot ve genel açılış

### CI kapıları

- mevcut personel CRUD/import/export
- profesyonel CRUD/hesap eşleme
- şirket ve işyeri izolasyonu
- object-store local/dual/R2
- upload güvenliği
- audit
- PDF ve CV
- paylaşım süresi/iptali
- restricted veri dışlama
- PostgreSQL migration/parity/rollback
- frontend unit/lint/build
- masaüstü/laptop/tablet/mobil Playwright
- eğitim, kurul, risk, sağlık, belge onay ve imza regresyonları

### Production açılış sırası

1. Kod deploy — bütün flag’ler kapalı
2. Sağlık/log kontrolü
3. Pilot allowlist tek test şirketi
4. Read-only kart
5. Fotoğraf/CV normal belge pilotu
6. PDF CV pilotu
7. Kontrollü paylaşım ayrı onay
8. Restricted veri genel açılıştan bağımsız ve kapalı
9. Kullanıcı kabulü
10. Sınırlı genişletme

## Acil rollback

Normal acil kapatma sırası:

1. `PERSONNEL_PROFILE_CARD_FORCE_OFF=true`
2. `PERSONNEL_PROFILE_CARD_ENABLED=false`
3. Alt özellik flag’lerini kapat
4. Pilot allowlist’i boşalt
5. Aktif paylaşım linklerini iptal et

Normal rollback sırasında:

- mevcut personel/profesyonel tablolarına downgrade uygulanmaz
- tarihsel profil, dosya, CV, paylaşım ve audit kayıtları silinmez
- R2 nesneleri topluca silinmez
- mevcut personel ekranı, Excel import ve eski API’ler çalışmaya devam eder

## İlk geliştirme PR’ının sınırı

Faz 2 PR’ı yalnız şunları içermelidir:

- kapalı feature flag + force-off + pilot allowlist
- salt okunur readiness servisi
- salt okunur minimum profil özeti API’si
- hassas alan dışlama/mask testleri
- şirket/OSGB erişim testleri
- flag-off eski ekran regresyonu
- teknik karar belgesi

Şunları içermemelidir:

- migration
- dosya yükleme
- CV üretme
- dış paylaşım
- adli sicil veya sağlık verisi
- mevcut Employee/IsgProfessional alan değişikliği
- production aktivasyonu
