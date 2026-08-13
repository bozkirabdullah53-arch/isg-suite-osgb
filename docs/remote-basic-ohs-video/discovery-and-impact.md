# Basic Occupational Health and Safety Training — uzaktan video modülü

Bu değişiklik, mevcut yüz yüze eğitim akışından bağımsız ve özellik bayrağı
kapalı başlayan bir pilot katmanıdır. Mevcut `TrainingSession`, katılımcı,
soru-sınav ve sertifika kayıtları değiştirilmez.

## Keşif sonucu

- Uygulama FastAPI + SQLAlchemy + React/Vite kullanıyor; PostgreSQL ve SQLite
  çalışma biçimleri mevcut.
- Firma, işyeri/şube, çalışan, kullanıcı, mevcut soru bankası ve PDF sertifika
  üreticisi zaten var.
- Kullanıcı ile çalışan arasında güvenilir bir doğrudan bağ bulunmadığından,
  uzaktan çalışan paneli için açıkça yetkilendirilen
  `remote_training_employee_access` eşleştirmesi eklendi. Eşleştirme, mevcut
  JWT tenant/RLS kapsamını genişletir; URL’deki çalışan kimliğine güvenilmez.
- NACE, SGK sicil ve tehlike sınıfı atama sırasında mevcut firma/işyeri
  kaynaklarından snapshot alınır. Eksik veri uydurulmaz; sertifika üretimi
  eksik tarihsel kimlikte durur.

## Yaşam döngüsü

`Draft → Uploading → Processing → Processing Failed / Ready for Review →
Published → Unpublished / Archived`

Video erişimi yalnızca kısa ömürlü imzalı JWT URL’si ile verilir. Kalıcı public
URL, depolama anahtarı veya çalışana ait doğrulama cevabı API çıktısına konmaz.
Çalışan ilerlemesi sunucuda saklanır; video açılması tek başına tamamlanma
sayılmaz. Tamamlama, yayımlanmış mevcut videoların eşik yüzdesi, varsa video içi
zorunlu sorular ve mevcut soru bankasına bağlanan final sınavı birlikte
değerlendirilerek hesaplanır.

## Etki ve geri alma

| Alan | Etki | Geri alma |
|---|---|---|
| Veritabanı | 0089–0091 uzaktan video/sector/katalog tablolarına ek olarak 0092 yalnızca yeni politika alanlarını ve `users.password_change_required` alanını ekler | `REMOTE_BASIC_OHS_STRICT_POLICY_FORCE_OFF=true`; migration geri alma yalnız kontrollü bakım penceresinde yapılır |
| Backend | Yeni `/api/v1/trainings/remote/*` router’ı | `REMOTE_BASIC_OHS_TRAINING_FORCE_OFF=true` veya enabled=false |
| Frontend | Mevcut Eğitimler ekranına yalnızca bayrak açıkken yeni sekme | Bayrağı kapatınca sekme ve pilot API akışı görünmez |
| Depolama | `company_id/remote-basic-ohs/...` altında özel anahtarlar | Yeni pilot kayıtları yayımdan kaldırılır; eski mevcut eğitim dosyalarına dokunulmaz |
| Mevcut eğitimler | `TrainingSession` ve mevcut PDF/sınav endpoint’leri değişmez | Kod geri alınsa bile yeni tablolar downgrade edilene kadar ayrı kalır |

## Ortak kural motoru ve Yüksekte Çalışma pilotu

- Mevcut firma programları migration sırasında `legacy` olarak kalır; mevcut
  eşikler, ilerleme kayıtları ve sınav davranışı değiştirilmez.
- Merkezi katalogdan firmaya yeni çalışma sürümü oluşturulduğunda kaynak paket,
  revizyon, `100%` video tamamlama, sıralı ders, video içi kontrol ve `70` puan
  sınav kuralı programa snapshot olarak yazılır. Sonradan katalogda yapılan
  değişiklik çalışanların tarihsel atamasını değiştirmez.
- `working-at-height-ohs` ilk pilot allowlist paketidir. Paket yayımlama,
  çalışan ataması, video ilerlemesi, video içi soru ve final sınavı strict
  bayrak açılmadan çalışan akışına geçemez.
- Geçici çalışan hesabı oluşturulursa parola yalnızca oluşturma yanıtında bir
  kez gösterilir. İlk girişte parola değişikliği zorunludur; parola
  değiştirilmeden uzaktan eğitim kaydına erişim verilmez.

Pilot bayrakları:

```text
REMOTE_BASIC_OHS_STRICT_POLICY_ENABLED=false
REMOTE_BASIC_OHS_STRICT_POLICY_FORCE_OFF=false
REMOTE_BASIC_OHS_STRICT_POLICY_PACKAGE_CODES=working-at-height-ohs
REMOTE_BASIC_OHS_STRICT_POLICY_PILOT_COMPANY_IDS=
```

Son iki allowlist alanı, pilotu önce tek bir firmaya açmak için kullanılır.
Bayraklar varsayılan ve Render yapılandırmasında kapalıdır; canlı çalışanlara
eğitim başlatmak için ayrıca manuel ve kontrollü açılış gerekir.

## Kontrollü pilot koşulları

1. `REMOTE_BASIC_OHS_TRAINING_ENABLED=true` yalnız pilot ortamında açılır;
   acil kapatma için `REMOTE_BASIC_OHS_TRAINING_FORCE_OFF=true` kullanılır.
2. Üretimde güvenli özel/uzak nesne depolama ve `ffprobe` bulunan bir worker
   sağlanır. Video işleme süresi okunmadan video yayımlanamaz.
3. Pilot şirket için önce çalışan kullanıcı–çalışan eşleştirmesi yapılır;
   ardından tek bir temel İSG programı, az sayıda video ve test ataması ile
   doğrulanır.
4. Tenant izolasyonu, imzalı URL süresi, ilerleme/sınav/sertifika ve rapor
   kontrolleri doğrulanmadan bayrak genelleştirilmez.

Bu çalışma alanındaki değişiklikler kontrollü yayın için hazırlanmıştır; canlı
ortama otomatik deploy veya GitHub push yapılmaz.
