# İBYS Başvurusu Kurumsal Belge Yükleme Rehberi

## Gerekli profil bilgileri

`company-profile.template.json` dosyası kopyalanarak `company-profile.json` adıyla doldurulur. Bu gerçek dosya Git'e eklenmez.

Zorunlu alanlar:

- Tam ticari unvan
- Vergi dairesi
- Vergi numarası
- MERSİS numarası
- Tebligat adresi
- Telefon
- Kurumsal e-posta
- Yetkili temsilci ad soyad
- Yetkili temsilci unvanı

## Zorunlu kurumsal ekler

Dosya isimleri aşağıdaki anahtar sözcükleri içermelidir:

- `ticaret-sicil-gazetesi.pdf`
- `faaliyet-belgesi.pdf`
- `vergi-levhasi.pdf`
- `imza-sirkuleri.pdf`

Ek olarak sunulması önerilenler:

- Teknik irtibat görevlendirme yazısı
- Marka tescil veya yazılım sahipliği beyanı
- Oda kayıt belgesi
- Yetkili temsilci iletişim yazısı

## Güvenlik

- Belgeler public repository'ye yüklenmez.
- TCKN içeren belgeler yalnız yetkili başvuru klasöründe tutulur.
- Paket üreticisi şirket profilini doğrular ve eksik belge varsa ZIP üretmez.
- Üretilen ZIP içindeki manifest her dosyanın SHA-256 değerini taşır.
- Vergi ve MERSİS numaraları manifestte yalnız son dört hanesi açık olacak şekilde maskelenir.

## Paket üretme

Repo kökünden:

```bash
python backend/scripts/build_ibys_application_bundle.py \
  --company-profile /gizli/klasor/company-profile.json \
  --attachments-dir /gizli/klasor/kurumsal-ekler \
  --output /gizli/klasor/isg-suite-ibys-basvuru.zip
```

Eksik bilgi, placeholder veya zorunlu kurumsal ek bulunursa komut hata kodu `2` ile durur. Başarılı çıktı dahi Bakanlık tescili anlamına gelmez; yalnız başvuru dosyasının eksiksiz paketlendiğini gösterir.
