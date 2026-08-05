# İBYS Entegratör Başvuru Hazırlık Dosyası

Bu klasör, İSG Suite OSGB yazılımının Çalışma ve Sosyal Güvenlik Bakanlığı İş Sağlığı ve Güvenliği Genel Müdürlüğüne yapılacak İBYS entegratör başvurusu için hazırlanmıştır.

## Kritik sınır

Bu dosya **Bakanlık tescili veya resmî İBYS teknik uygunluğu iddia etmez**. Bakanlığın güncel resmî veri seti, servis sözleşmesi, kimlik doğrulama yöntemi ve test ortamı erişimi henüz projeye teslim edilmemiştir.

Başvuru hazırlığı iki ayrı kapıdan oluşur:

1. **Başvuruya hazır kurumsal ve teknik dosya:** Yazılım mimarisi, veri güvenliği, tenant izolasyonu, test kanıtları, demo senaryoları ve sürümlü aday veri eşleme profili.
2. **Resmî teknik sözleşme uyarlaması:** İSGGM tarafından teslim edilen veri-seti kodları, alan adları, endpoint, kimlik doğrulama, hata kodları ve kabul senaryolarının sisteme işlenmesi.

## Dosya indeksi

- `BASVURU_DOSYASI_KONTROL_LISTESI.md`: Kurumsal, hukuki ve teknik evrakların sahiplik/durum listesi.
- `BASVURU_SAHIBI_BILGI_VE_BELGE_FORMU.md`: Gerçek şirket bilgileri, yetkili/teknik irtibat ve zorunlu belge teslim formu.
- `KANIT_KAPILARI_KAPANIS_FORMU.md`: Hukuk/KVKK, dış yetki smoke, yetkili imza ve İSGGM randevu onaylarının kanıtlı kapanış formu.
- `TEKNIK_UYGUNLUK_MATRISI.md`: Mevcut sistem kabiliyetleri ile başvuru kanıtlarının eşlemesi.
- `DEMO_KABUL_SENARYOLARI.md`: Bakanlık sunumu/test görüşmesi için kabul ve ret senaryoları.
- `RESMI_SOZLESME_TESLIM_TUTANAGI.md`: Resmî veri şeması ve servis sözleşmesi alındığında doldurulacak kontrol tutanağı.
- `company-profile.template.json`: Gerçek şirket bilgileri için repoya alınmayan profil şablonu.
- `application-manifest.json`: Makine tarafından okunabilir başvuru durumu, puan politikası ve kapanış kapıları.

## Teknik demo API'leri

Yalnız global yönetici ve OSGB yöneticisi rolleri erişebilir:

- `GET /api/v1/ibys-application/profile`
- `GET /api/v1/ibys-application/readiness`
- `POST /api/v1/ibys-application/preflight`
- `POST /api/v1/ibys-application/validate/{dataset_code}`
- `POST /api/v1/ibys-application/envelope/{dataset_code}`

Bu uç noktalar harici İBYS çağrısı yapmaz. Aday kayıtları zorunlu alan, deterministik fingerprint ve idempotency açısından doğrular.

`preflight` uç noktası şirket profil değerlerini yanıta geri koymadan eksik alanları, eksik belge gruplarını, kanıt kapılarını, başvuru ZIP'i üretilebilirliğini ve %80–%100 hazırlık puanını gösterir. Boolean onay kapıları yetkili kullanıcı beyanıdır; nihai dosyada belge/audit kanıtıyla doğrulanmalıdır.

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
- Başvuru dilekçesi imzaya hazır olmalı.
- KVKK/veri güvenliği ve sistem mimarisi ekleri hazırlanmalı ve yetkili onayı alınmalı.
- İSGGM ile resmî veri sözleşmesi/test ortamı talep yazısı hazırlanmalı.
- Randevu talep iletişim metni ve sunum gündemi nihai olarak onaylanmalı.
- Dış ortamda yetkisiz erişim ve rol kapsamı smoke kanıtı tamamlanmalı.
- Dört nihai kanıt kapısı tarih, doğrulayan kişi, kanıt referansı ve SHA-256 ile kapatılmalı.

Resmî İBYS uygunluğu ise ancak Bakanlık sözleşmesi ve kabul testleri tamamlandıktan sonra ayrıca ilan edilebilir.
