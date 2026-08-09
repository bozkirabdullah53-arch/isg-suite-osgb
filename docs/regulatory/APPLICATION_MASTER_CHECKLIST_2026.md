# İSG SUITE — İBYS + İSBS/e‑Reçete Başvuru Master Checklist (2026)

**Doğrulama tarihi:** 09.08.2026  
**Amaç:** İSG SUITE'in ÇSGB İBYS entegratör tescili ile Sağlık Bakanlığı KTS/İSBS/e‑Reçete süreçlerine kontrollü hazırlanması.  
**Kural:** Bu doküman başvuru/tescil belgesi değildir. Bakanlıkça verilmemiş hiçbir test kodu, onay veya protokol varmış gibi kabul edilmez.

## 1. Yazılım tarafında tamamlanan başvuru altyapısı

- [x] OSGB/işyeri tenant ve görev kapsamı
- [x] E‑imza altyapısı: kaynak SHA‑256, tek kullanımlık talep, sertifika meta, doğrulama, OCSP/CRL/TSA seçenekleri, belge kilidi/audit
- [x] Sağlık hassas alan şifreleme katmanı
- [x] İşyeri hekimi rol ayrımı ve reçete yaşam döngüsü
- [x] Reçete gönderim/attempt/hata kayıt modelleri
- [x] İBYS legacy generic adapter'ın resmî entegrasyon olarak kabul edilmemesi
- [x] Resmî endpoint + resmî profil + Bakanlık test/access code + explicit enable olmadan gönderimi kapatan fail‑closed authority gate
- [x] Canonical payload SHA‑256 + request id + idempotency key zarfı
- [x] Resmî entegrasyon kimlikleri için ayrı şifreli Regulatory Identity Vault
- [x] Salt okunur başvuru/veri preflight raporu
- [x] Secret değerlerini dışarı çıkarmayan readiness çıktısı

## 2. ÇSGB İBYS — başvuru sahibi tarafından tamamlanacaklar

ÇSGB'nin güncel SSS'si, entegratör olmak isteyen yazılım firmalarının İBYS internet sitesindeki **güncel başvuru evraklarını** hazırlayıp İş Sağlığı ve Güvenliği Genel Müdürlüğünden randevu alarak başvurmasını ister.

- [ ] Başvuru günü `ibys.csgb.gov.tr` / İSGGM üzerinden **güncel evrak seti** son kez doğrulandı.
- [ ] Evrak seti eksiksiz dolduruldu, yetkili imza/kaşe kontrolleri yapıldı.
- [ ] İSGGM entegratör başvuru randevusu alındı.
- [ ] Başvuruda kullanılacak ürün adı/sürümü sabitlendi ve release SHA kayda alındı.
- [ ] Bakanlığın vereceği güncel veri sözlüğü / test profili / test erişimi teslim alındı.
- [ ] İBYS dataset adapter yalnız bu resmî profile karşı geliştirildi.
- [ ] İSG profesyoneli e‑İmza veya Mobil İmza akışı resmî gönderim profiline bağlandı.
- [ ] Test kabul/ret cevapları, tekrar gönderim ve makbuz/audit senaryoları tamamlandı.
- [ ] Tescil/entegratör numarası alındıktan sonra production gate açıldı.

**Resmî kaynak:** ÇSGB İSGGM SSS, sorular 81–86; https://www.csgb.gov.tr/tr/sikca-sorulan-sorular/is-sagligi-ve-guvenligi-genel-mudurlugu/

## 3. Sağlık Bakanlığı KTS / İSBS — başvuru evrakı

07.04.2025 tarihli KTS Kayıt Aşamaları sayfası ve KTS Kılavuzu/Ek‑5 esas alınmıştır.

- [ ] Kuruluş Ticaret Sicil Gazetesi
- [ ] Güncel Ticaret Sicil Gazetesi
- [ ] SGK işyeri tescil belgesi/numarası
- [ ] Son üç yıla ait, kılavuzdaki doğrulama/onay şartlarını sağlayan bilançolar
- [ ] SBYS Yetkili Belgesi (e‑Devlet erişimi olan yetkili personel)
- [ ] SBYS Yazılım Listesi — ürün türü **İSBS** olarak doğru tanımlı
- [ ] Gerekliyse vekâletname / imza yetkisi kanıtı
- [ ] TÜRKAK kapsamı uygun **TS ISO/IEC 27001** belgesi
- [ ] **TS ISO/IEC 15504 SPICE ≥ Seviye 2** veya **CMMI ≥ Seviye 3** kanıtı
- [ ] Firma yönetici/yetkili/personel bilgileri
- [ ] Gizlilik Sözleşmesi — kılavuza göre iki asıl nüsha, gerekli paraf/kaşe/imza; Bakanlıkta karşılıklı imza
- [ ] Yurt içinde geliştirilen yazılım için bilgisayar programı/veritabanı kayıt‑tescil belgesi değerlendirildi (kılavuzda ihtiyari)
- [ ] Yabancı ürün söz konusuysa apostilli distribütörlük belgesi (İSG SUITE yerli geliştirme ise uygulanmaz)
- [ ] Ek‑1 güncel resmi yazı örneği kullanıldı
- [ ] Ek‑2 güncel SBYS Yetkili Belgesi kullanıldı
- [ ] Ek‑3 güncel SBYS Yazılım Listesi kullanıldı
- [ ] Ek‑4 güncel Gizlilik Sözleşmesi kullanıldı
- [ ] Ek‑5 belge listesine karşı son çapraz kontrol yapıldı

**Resmî kaynak:** https://kayittescil.saglik.gov.tr/TR-5571/kts-kayit-asamalari.html

## 4. KTS ön kayıt sonrasında yapılacak teknik testler

KTS kılavuzuna göre eksiksiz başvuru ve gizlilik sürecinden sonra yazılım için ön kayıt oluşturulur; Bakanlıkça **yazılım erişim test kodu** verilir ve veri aktarımı / sağlık bilişimi standart uyum testleri yürütülür. Testler geçildikten sonra production yazılım erişim kodu verilir.

- [ ] Bakanlık test kılavuzu teslim alındı ve sürüm/hash ile arşivlendi.
- [ ] `ISBS_KTS_SOFTWARE_ACCESS_TEST_CODE` secret store'a girildi.
- [ ] `ISBS_ERECETE_PROFILE_VERSION` resmî doküman sürümüne sabitlendi.
- [ ] Test endpoint secret/env üzerinden tanımlandı; kaynak koda yazılmadı.
- [ ] Sadece sentetik/Bakanlığın verdiği test verisi ile test yapıldı.
- [ ] Başarı/ret/hata/timeout/retry/idempotency senaryoları kanıtlandı.
- [ ] Test sonucu ve Bakanlık kabul kanıtı arşivlendi.
- [ ] Production erişim kodu ancak test kabulünden sonra secret store'a girildi.
- [ ] Production send switch dört göz/onay prosedürü ile açıldı.

## 5. E‑Reçete / RRS

Sağlık Bakanlığı Kayıt ve Tescil Biriminin resmî duyurusuna göre entegrasyonu olmayan SBYS üreticileri E‑Reçete (Renkli Reçete Sistemi/RRS) entegrasyonunu gerçekleştirmelidir; güncel teknik doküman resmî RRS kanalından alınmalıdır.

- [ ] Güncel RRS/e‑Reçete entegrasyon dokümanı yetkili kaynaktan alındı.
- [ ] Uygulamadaki legacy `medula` adlandırması ile resmî Sağlık Bakanlığı RRS protokolü birbirine karıştırılmadı.
- [ ] Wire format / auth / endpoint / hata kodu **tahmin edilmedi**; resmî dokümana birebir adapter yazıldı.
- [ ] Hekim yetkisi ve işyeri görevlendirmesi test edildi.
- [ ] Hasta/çalışan resmî kimliği yalnız şifreli Regulatory Identity Vault üzerinden adapter'a verildi.
- [ ] Tanı/ilaç/kullanım verileri yalnız resmî profilin gerektirdiği alanlarla gönderildi.
- [ ] Reçete numarası/yanıt/hata/correlation bilgisi izlenebilir kaydedildi.

**Resmî kaynak:** https://kayittescil.saglik.gov.tr/TR-63630/01022020-e-recete-entegrasyonu-hk-tum-sbys-ureticilerine.html

## 6. Başvurudan önce çalıştırılacak teknik kapı

```bash
cd backend
python scripts/regulatory_application_readiness.py --strict
```

İstenirse yalnız bir OSGB için:

```bash
python scripts/regulatory_application_readiness.py --osgb-id <ID> --strict
```

`--strict` aşağıdaki durumda non‑zero döner:
- source-controlled application layer blocker varsa,
- canlı/veri tabanı preflight'ında yüksek öncelikli yerel veri bulgusu varsa.

Kurumsal sertifika veya henüz Bakanlıkça verilmemiş test kodları **software failure** olarak taklit edilmez; raporda `external_required` veya `authority_pending` olarak ayrı gösterilir.
