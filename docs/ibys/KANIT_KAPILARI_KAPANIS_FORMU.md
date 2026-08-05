# İBYS Başvuru Hazırlığı — Kanıt Kapıları Kapanış Formu

Bu form, başvuru hazırlık puanının %95’ten %100’e çıkarılmasında kullanılan dört nihai kanıt kapısını belgelemek için hazırlanmıştır. Kutucuk işaretlemek tek başına yeterli değildir; her kapı için tarih, doğrulayan kişi ve kanıt referansı bulunmalıdır.

## Kapı 1 — Hukuk ve KVKK onayı (%2)

- [ ] KVKK veri envanteri incelendi.
- [ ] Hukuki sebepler ve veri işleme amaçları onaylandı.
- [ ] Kesin saklama süreleri onaylandı.
- [ ] Saklama-imha politikası onaylandı.
- [ ] Aydınlatma, açık rıza gerekliliği ve veri aktarım hükümleri değerlendirildi.

| Alan | Değer |
|---|---|
| Onaylayan kişi / birim |  |
| Unvan |  |
| Onay tarihi |  |
| Kanıt dosyası / karar no |  |
| Kanıt SHA-256 |  |
| Açık kalan şart |  |

## Kapı 2 — Yetkisiz erişim ve rol kapsamı smoke (%1)

- [ ] Kimliksiz `GET /api/v1/ibys-application/profile` isteği `401/403` verdi.
- [ ] Kimliksiz `POST /api/v1/ibys-application/preflight` isteği `401/403` verdi.
- [ ] Yetkisiz rol veri-seti profilini göremedi.
- [ ] OSGB yöneticisi başka OSGB kapsamı için paket üretemedi.
- [ ] Yanıtta şirket profil değerleri, vergi numarası veya secret bulunmadı.

| Alan | Değer |
|---|---|
| Test ortamı ve URL |  |
| Test tarihi |  |
| Uygulama commit SHA |  |
| Testi yapan |  |
| Ekran görüntüsü / rapor referansı |  |
| Kanıt SHA-256 |  |
| Sonuç |  |

## Kapı 3 — Başvuru dilekçesi yetkili imzası (%1)

- [ ] Ticari unvan resmî belgelerle birebir eşleşiyor.
- [ ] Vergi ve MERSİS numarası doğrulandı.
- [ ] Tebligat ve iletişim bilgileri doğrulandı.
- [ ] İmzalayan kişinin yetkisi kontrol edildi.
- [ ] Dilekçe ıslak imza veya güvenli e-imza ile imzalandı.

| Alan | Değer |
|---|---|
| İmzalayan |  |
| Unvan |  |
| İmza tarihi |  |
| İmza yöntemi |  |
| İmzalı dosya adı |  |
| Dosya SHA-256 |  |

## Kapı 4 — İSGGM randevu paketi nihai onayı (%1)

- [ ] Güncel başvuru evrak listesi İSGGM’den teyit edildi.
- [ ] Randevu talep metni nihai hâle getirildi.
- [ ] Teknik sunum gündemi hazırlandı.
- [ ] Başvuru ZIP manifesti kontrol edildi.
- [ ] Gönderim kanalı, muhatap ve tarih yetkili tarafından onaylandı.

| Alan | Değer |
|---|---|
| Onaylayan |  |
| Onay tarihi |  |
| Randevu talep referansı |  |
| Başvuru ZIP dosya adı |  |
| Başvuru ZIP SHA-256 |  |
| Gönderim / teslim tarihi |  |

## Nihai kapanış

Aşağıdaki koşulların tümü gerçekleşmeden `ready_for_submission=true` kabul edilmez:

- Şirket profili eksiksiz ve şablon değerlerden temizdir.
- Dört zorunlu kurumsal belge doğrulanmıştır.
- Hukuk/KVKK onayı kanıtlanmıştır.
- Dış ortam yetkilendirme smoke testi kanıtlanmıştır.
- Başvuru dilekçesi yetkili tarafından imzalanmıştır.
- İSGGM randevu paketi nihai olarak onaylanmıştır.
- ZIP içindeki bütünlük manifesti kontrol edilmiştir.

> Başvuru hazırlığının %100 olması, Bakanlık tescili veya resmî İBYS teknik uygunluğu anlamına gelmez. Resmî sözleşme, test erişimi ve Bakanlık kabul süreci ayrı aşamadır.
