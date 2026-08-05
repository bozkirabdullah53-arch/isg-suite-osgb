# İBYS Entegratör Başvuru Hazırlık Dosyası

Bu klasör, İSG Suite OSGB yazılımının Çalışma ve Sosyal Güvenlik Bakanlığı İş Sağlığı ve Güvenliği Genel Müdürlüğüne yapılacak İBYS entegratör başvurusu için hazırlanmıştır.

## Güncel kanıt durumu

- Kanıt bazlı başvuru hazırlığı: **%81**
- Teknik profil, fail-closed ZIP, ön kontrol ve katı kanıt defteri: tamamlandı.
- GitHub Actions gerçek dış anonim yetkilendirme smoke: tamamlandı.
- Şirket profili ve zorunlu belgeler tamamlandığında doğrulanmış eşik: **%96**
- Hukuk/KVKK, yetkili imza ve randevu paketi onayı tamamlandığında hedef: **%100**

## Kritik sınır

Bu dosya **Bakanlık tescili veya resmî İBYS teknik uygunluğu iddia etmez**. Bakanlığın güncel resmî veri seti, servis sözleşmesi, kimlik doğrulama yöntemi ve test ortamı erişimi henüz projeye teslim edilmemiştir.

Başvuru hazırlığı iki ayrı kapıdan oluşur:

1. **Başvuruya hazır kurumsal ve teknik dosya:** Yazılım mimarisi, veri güvenliği, tenant izolasyonu, test kanıtları, demo senaryoları ve sürümlü aday veri eşleme profili.
2. **Resmî teknik sözleşme uyarlaması:** İSGGM tarafından teslim edilen veri-seti kodları, alan adları, endpoint, kimlik doğrulama, hata kodları ve kabul senaryolarının sisteme işlenmesi.

## Dosya indeksi

- `BASVURU_DOSYASI_KONTROL_LISTESI.md`: Kurumsal, hukuki ve teknik evrakların sahiplik/durum listesi.
- `BASVURU_SAHIBI_BILGI_VE_BELGE_FORMU.md`: Gerçek şirket bilgileri, yetkili/teknik irtibat ve zorunlu belge teslim formu.
- `KANIT_KAPILARI_KAPANIS_FORMU.md`: Hukuk/KVKK, dış yetki smoke, yetkili imza ve İSGGM randevu onaylarının kanıtlı kapanış formu.
- `EXTERNAL_AUTH_SMOKE_KANITI.md`: Gerçek GitHub runner dış smoke sonucu, run/artifact/hash zinciri ve kapsam sınırı.
- `TEKNIK_UYGUNLUK_MATRISI.md`: Mevcut sistem kabiliyetleri ile başvuru kanıtlarının eşlemesi.
- `DEMO_KABUL_SENARYOLARI.md`: Bakanlık sunumu/test görüşmesi için kabul ve ret senaryoları.
- `RESMI_SOZLESME_TESLIM_TUTANAGI.md`: Resmî veri şeması ve servis sözleşmesi alındığında doldurulacak kontrol tutanağı.
- `company-profile.template.json`: Gerçek şirket bilgileri için repoya alınmayan profil şablonu.
- `evidence-ledger.template.json`: Belge ve nihai kanıt kapıları için hassas veri içermeyen kanıt defteri şablonu.
- `application-manifest.json`: Makine tarafından okunabilir başvuru durumu, puan politikası ve kapanış kapıları.

## Teknik demo ve doğrulama API'leri

Yalnız global yönetici ve OSGB yöneticisi rolleri erişebilir:

- `GET /api/v1/ibys-application/profile`
- `GET /api/v1/ibys-application/readiness`
- `POST /api/v1/ibys-application/preflight`
- `POST /api/v1/ibys-application/evidence/validate`
- `POST /api/v1/ibys-application/preflight/verified`
- `POST /api/v1/ibys-application/validate/{dataset_code}`
- `POST /api/v1/ibys-application/envelope/{dataset_code}`

Bu uç noktalar harici İBYS çağrısı yapmaz. Aday kayıtları zorunlu alan, deterministik fingerprint ve idempotency açısından doğrular.

`preflight` uç noktası şirket profil değerlerini yanıta geri koymadan eksik alanları, eksik belge gruplarını, kanıt kapılarını, başvuru ZIP'i üretilebilirliğini ve %80–%100 hazırlık puanını gösterir. Bu uç noktadaki boolean kapılar yalnız ön çalışma içindir.

Nihai kapanışta `evidence/validate` ve `preflight/verified` kullanılmalıdır. Katı mod; doğrulayan kişi, saat dilimli ISO tarih, kanıt referansı ve geçerli SHA-256 bulunmayan bir kapıya puan vermez. Kanıt defterinde vergi/MERSİS/TCKN, parola, secret, API anahtarı veya token anahtarı bulunursa doğrulama reddedilir.

## Dış yetkilendirme smoke kanıtı

Staging veya üretim ortamında korunan başvuru rotalarının anonim kullanıcıya veri vermediğini doğrulamak için:

```bash
cd backend
python scripts/ibys_external_auth_smoke.py \
  --base-url https://isg-suite-api-staging.onrender.com \
  --output ../docs/ibys/kanitlar/external-auth-smoke.json
```

Araç:

- Yalnız HTTPS hedefi kabul eder.
- URL içinde kullanıcı adı, parola, query veya fragment bulunmasını reddeder.
- Authorization başlığı göndermez.
- Yanıt gövdesini kanıt dosyasına kaydetmez.
- Korunan rota `401/403` dışında yanıt verirse veya veri işareti sızdırırsa başarısız olur.
- Kanıt JSON’unu `evidence_sha256` ile mühürler.

Otomatik GitHub Actions smoke run `30982016480` başarıyla tamamlanmıştır. Üç korunan rota `401` döndürmüş; taşınabilir dosya checksum’u ve iç kanıt mührü bağımsız olarak doğrulanmıştır. Ayrıntılar `EXTERNAL_AUTH_SMOKE_KANITI.md` dosyasındadır.

## Kanıt defteri doğrulaması

`evidence-ledger.template.json` güvenli çalışma alanında `evidence-ledger.json` adıyla kopyalanır ve gerçek kanıt referanslarıyla doldurulur. Gerçek şirket profili ve kanıt defteri şu komutla doğrulanır:

```bash
cd backend
python scripts/validate_ibys_application_evidence.py \
  --company-profile ../docs/ibys/company-profile.json \
  --evidence-ledger ../docs/ibys/evidence-ledger.json \
  --output ../docs/ibys/kanitlar/verified-preflight-report.json
```

Komut ancak:

- Şirket profili eksiksizse,
- Dört zorunlu kurumsal belge geçerli kanıt bilgileriyle doğrulanmışsa,
- Hukuk/KVKK, dış smoke, dilekçe imzası ve randevu paketi kapıları kanıtlarıyla kapanmışsa

`ready_for_submission=true` ve `%100` sonucu verir. Rapor şirket profil değerlerini geri yazmaz.

## İmzaya hazır başvuru ZIP'i

Gerçek şirket profili ve kurumsal ekler repoya eklenmez. Yerel veya güvenli yönetim ortamında aşağıdaki komut kullanılır:

```bash
cd backend
python scripts/build_ibys_application_bundle.py \
  --company-profile ../docs/ibys/company-profile.json \
  --attachments-dir ../docs/ibys/kurumsal-ekler \
  --output ../docs/ibys/ibys-basvuru-paketi.zip
```

Paket üretimi şu durumlarda fail-closed durur:

- Zorunlu şirket profil alanlarından biri boşsa,
- Profilde köşeli parantezli şablon değer kalmışsa,
- Ticaret sicili, faaliyet belgesi, vergi levhası veya imza sirkülerinden biri bulunmazsa.

Başarılı ZIP içinde dosya bazlı SHA-256 bütünlük manifesti bulunur ve `official_registration_claim=false` sınırı korunur.

## Başvuruya hazır sayılma kuralı

Başvuru hazırlığı %100 sayılabilmesi için:

- Teknik aday profil ve demo kabul paketi CI + staging üzerinde doğrulanmış olmalı.
- Kurumsal evraklar yetkili kişi tarafından temin edilip kontrol edilmeli.
- Başvuru dilekçesi yetkili tarafından imzalanmalı.
- KVKK/veri güvenliği ve sistem mimarisi ekleri hazırlanmalı ve yetkili onayı alınmalı.
- İSGGM ile resmî veri sözleşmesi/test ortamı talep yazısı hazırlanmalı.
- Randevu talep iletişim metni ve sunum gündemi nihai olarak onaylanmalı.
- Dış ortamda yetkisiz erişim ve rol kapsamı smoke kanıtı tamamlanmalı.
- Dört nihai kanıt kapısı tarih, doğrulayan kişi, kanıt referansı ve SHA-256 ile kapatılmalı.
- Katı doğrulama raporu `%100` ve `ready_for_submission=true` üretmeli.

Resmî İBYS uygunluğu ise ancak Bakanlık sözleşmesi ve kabul testleri tamamlandıktan sonra ayrıca ilan edilebilir.
