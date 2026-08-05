# İBYS Entegratör Başvurusu — Başvuru Sahibi Bilgi ve Belge Formu

> Bu form gerçek başvuru sahibi şirket tarafından doldurulur. Gerçek şirket bilgileri ve belge dosyaları GitHub deposuna yüklenmez; yalnız güvenli başvuru çalışma alanında tutulur.

## 1. Şirket kimlik bilgileri

| Alan | Değer | Kontrol eden | Tarih |
|---|---|---|---|
| Tam ticari unvan |  |  |  |
| Vergi dairesi |  |  |  |
| Vergi numarası |  |  |  |
| MERSİS numarası |  |  |  |
| Ticaret sicil müdürlüğü ve sicil numarası |  |  |  |
| Kayıtlı tebligat adresi |  |  |  |
| Telefon |  |  |  |
| Kurumsal e-posta |  |  |  |
| İnternet sitesi |  |  |  |

## 2. Yetkili ve teknik irtibat

| Alan | Değer | Kontrol eden | Tarih |
|---|---|---|---|
| Başvuruyu imzalayacak yetkili ad-soyad |  |  |  |
| Yetkilinin unvanı |  |  |  |
| Yetki dayanağı |  |  |  |
| Teknik sorumlu ad-soyad |  |  |  |
| Teknik sorumlu e-posta |  |  |  |
| Teknik sorumlu telefon |  |  |  |
| KVKK / hukuk irtibatı |  |  |  |
| Bilgi güvenliği irtibatı |  |  |  |

## 3. Zorunlu kurumsal ekler

Başvuru paket üreticisinin otomatik algılaması için dosya adlarında belirtilen anahtar kelimeler korunmalıdır.

| Belge | Önerilen dosya adı | Var | Güncel/geçerli | SHA-256 kaydedildi | Kontrol eden |
|---|---|---:|---:|---:|---|
| Ticaret Sicil Gazetesi / sicil belgesi | `ticaret-sicil-gazetesi.pdf` | ☐ | ☐ | ☐ |  |
| Güncel faaliyet belgesi | `faaliyet-belgesi.pdf` | ☐ | ☐ | ☐ |  |
| Vergi levhası | `vergi-levhasi.pdf` | ☐ | ☐ | ☐ |  |
| İmza sirküleri / yetki belgesi | `imza-sirkuleri.pdf` | ☐ | ☐ | ☐ |  |
| Yetkili ve teknik irtibat yazısı | `yetkili-teknik-irtibat-yazisi.pdf` | ☐ | ☐ | ☐ |  |

## 4. Ek teyitler

- [ ] İSGGM’den güncel başvuru evrak listesi yazılı olarak teyit edildi.
- [ ] Evrakların güncellik süreleri kontrol edildi.
- [ ] Belge bütünlük hash’leri kaydedildi.
- [ ] Belgelerde gereksiz kişisel veri bulunmadığı kontrol edildi.
- [ ] Başvuru dilekçesindeki şirket bilgileri resmî belgelerle birebir karşılaştırıldı.
- [ ] Randevu talep metnindeki iletişim bilgileri doğrulandı.

## 5. Güvenli çalışma kuralı

1. Doldurulmuş şirket profili `docs/ibys/company-profile.json` adıyla yalnız güvenli yerel çalışma alanında tutulur.
2. Gerçek belgeler `docs/ibys/kurumsal-ekler/` altında yalnız güvenli yerel çalışma alanında tutulur.
3. Bu yollar `.gitignore` kapsamındadır ve repoya gönderilmez.
4. Başvuru ZIP’i üretildikten sonra `00-BUNDLE-MANIFEST.json` içindeki SHA-256 değerleri kontrol edilir.
5. Paket yalnız yetkili imza ve hukuk/KVKK kapanışından sonra gönderime alınır.

## 6. Başvuru sahibi beyanı

Bu formdaki bilgilerin resmî şirket kayıtlarıyla uyumlu olduğunu ve başvuru paketinde kullanılmasını onaylıyorum.

- Yetkili ad-soyad:
- Unvan:
- Tarih:
- İmza / güvenli e-imza:
