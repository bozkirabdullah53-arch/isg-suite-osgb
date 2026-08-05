# Faz 1 — Mevcut Sistem Analiz Raporu

**Tarih:** 5 Ağustos 2026  
**Kapsam:** Eğitim, NACE, tehlike sınıfı, konu, süre, sınav, sonuç, katılım belgesi ve PDF veri zinciri  
**Durum:** Tamamlandı. Ürün kodu değiştirilmemiştir.

## Yönetici özeti

Mevcut sistem tek bir onaylı ve sürümlü eğitim planından sınav ile sertifika üretmemektedir. Seçilen kesin NACE anahtarı canlı runtime resolver tarafından çoğunlukla geniş bir sektör profil koduna dönüştürülerek `training_sessions.sector` alanına yazılmaktadır. Bu nedenle kesin NACE kodu, açıklaması ve tarihsel sınıflandırması kaybolmaktadır.

Eğitim konuları eğitim kaydına bağlı satırlar olarak saklanmamakta, PDF üretildiği anda güncel Python kataloglarından yeniden oluşturulmaktadır. Mevcut 20 soruluk sınav dağılımı `5 sabit temel + 5 ortak + 5 tehlike/teknik + 5 sektör` biçimindedir; zorunlu `5 temel + 15 NACE/sektör teknik` kuralı uygulanmamaktadır.

Production soru bankasında yayımlanmış soru yoktur. Mevcut sınav öğelerinin tamamı paketlenmiş fallback JSON sorularından oluşmaktadır. Runtime katmanı doğrudan sektör sorusu yetersizse yakın kabul edilen bir alias profile, ardından `genel_uretim` havuzuna geçebilmektedir.

Katılım belgesi endpointi katılım, sınava girme, puan, başarı ve geçme koşulunu doğrulamadan belge üretmektedir. PDF her durumda kişinin eğitimi “başarıyla tamamlayarak ... almaya hak kazandığını” yazmaktadır.

## İncelenen ana bileşenler

- `backend/app/api/trainings.py`
- `backend/app/api/training_question_bank.py`
- `backend/app/models/entities.py`
- `backend/app/schemas/training.py`
- `backend/app/schemas/training_question_bank.py`
- `backend/app/services/training_topics.py`
- `backend/app/services/training_sector_catalog.py`
- `backend/app/services/training_question_bank.py`
- `backend/app/services/training_exam_pdf.py`
- `backend/app/services/training_pdfs.py`
- `backend/app/services/training_pdf_premium.py`
- `backend/app/services/training_runtime_patches.py`
- `backend/app/services/special_training_profiles.py`
- `backend/app/services/data/nace_sectors.json`
- `backend/app/services/data/training_exam_fallback/*.json`
- `backend/alembic/versions/0068_training_question_bank.py`
- `frontend/src/training.jsx`
- `frontend/src/training_question_bank.jsx`
- `frontend/src/training_question_bank_logic.js`
- `frontend/src/training_pro.css`
- `frontend/public/training-sectors.json`
- Eğitim, soru bankası, runtime patch, PostgreSQL/Alembic ve frontend testleri

## Mevcut veri akışı

### Eğitim oluşturma

1. Frontend NACE kataloğunu API veya statik paket üzerinden yükler.
2. Kullanıcı `nace_XX_XX_XX` anahtarı seçer.
3. Frontend katalog tehlike sınıfını ve beş profil konusunu gösterir.
4. Backend runtime resolver NACE anahtarını geniş profil koduna dönüştürür.
5. Eğitim kaydı kesin NACE yerine profil/legacy anahtarı saklar.
6. Süre tehlike sınıfına göre 8, 12 veya 16 ders saati olarak hesaplanır.
7. Konu ve konu süreleri kalıcı eğitim planı satırları olarak saklanmaz.

### Sınav

1. Son geçerli 20 soruluk snapshot varsa aynen kullanılır.
2. Yoksa ilk beş sabit temel soru eklenir.
3. Kalan 15 soru 5 ortak, 5 tehlike/teknik ve 5 sektör kovasından seçilir.
4. Veritabanı sorusu yoksa veya yetmezse paketlenmiş fallback sorular kullanılır.
5. Runtime alias katmanı sektör havuzunu başka profile veya `genel_uretim` havuzuna genişletebilir.
6. Sorular, seçenekler, cevaplar, açıklamalar, kaynaklar ve kapsamlar snapshot içinde dondurulur.
7. PDF yazılı sınav ve cevap anahtarı üretir; katılımcı cevap modeli ve çevrim içi sonuç hesaplama zinciri yoktur.

### Katılım belgesi

1. Yalnız katılımcı varlığı kontrol edilir.
2. Konular PDF anında güncel profilden yeniden oluşturulur.
3. Üst süre `duration_hours` alanından, konu dakikaları güncel tehlike kuralından gelir.
4. Belge numarası PDF üretim gününe ve sıraya göre yeniden oluşturulur; kalıcı katılımcı sertifika numarası kullanılmaz.
5. Katılım, puan ve başarı kontrol edilmeden başarı cümlesi basılır.

## Production toplu ölçüm sonuçları

Kişisel veri kullanılmadan yapılan read-only sorgular:

- Eğitim: **18**
- Planlanan: **18**, tamamlanan: **0**
- Şube/işyeri kimliği bulunan eğitim: **0**
- Katılımcı: **36**
- `attended=true`: **0**
- Puanı bulunan: **0**
- Başarı sonucu bulunan: **0**
- Sertifika numarası atanmış: **36**
- Eğitim düzeyinde `attendance_verified=true`: **18**
- Eğitim düzeyinde `success_verified=true`: **18**
- Soru bankası: **0**
- Yayımlanmış soru: **0**
- Sınav snapshotı: **4**
- Snapshot öğesi: **65**
- Tarihsel 15 soruluk snapshot: **3 / 45 öğe**
- Güncel 20 soruluk snapshot: **1 / 20 öğe**
- Veritabanı sorusuna bağlı öğe: **0**
- Paketlenmiş fallback öğesi: **65**

Production eğitimlerinin tamamı kesin `nace_*` anahtarı yerine profil/legacy anahtarı saklamaktadır.

## Zorunlu 15 sorunun yanıtları

1. **NACE gerçekten NACE'ye özel soru üretmiyor.** Mimari doğrudan NACE kapsamını desteklese de production bankası boştur; canlı akış profil/alias fallback kullanır.
2. Sorular yalnız tek etiketle seçilmese de gerçek kullanım geniş sektör profillerine dayanmaktadır.
3. Sistem sabit temel, rastgele DB seçimi, statik fallback ve değişmez snapshot karışımıdır.
4. Katı snapshot API havuz eksikliğinde durur; kullanıcı PDF yolu fallback ile devam eder.
5. **İlgisiz soru seçilebilir.** Örnekler aşağıdadır.
6. Konular NACE → geniş profil → beş konu zinciriyle üretilir; eğitim kaydına snapshot olarak yazılmaz.
7. Gerçek eğitim konu satırı olmadığı için sertifika-konu eşitliği kanıtlanamaz.
8. Süre etiketi ve konu dakika dağılımı farklı kaynaklardan geldiği için kalıcı bütünlük garantisi yoktur.
9. Tehlike sınıfı 8/12/16 ders saatini etkiler; başlangıç-bitiş saati, mola ve günlük oturum yoktur.
10. NACE güncellemesi desteklenmez; frontend çoğu alan değişikliğinde yeni kayıt oluşturur, açık invalidation akışı yoktur.
11. Katalog veya kayıt değişikliğinden sonra sertifika tutarlılığı bozulabilir.
12. Geçerli 20 soruluk snapshot yeniden açıldığında korunur; eski 15 soruluk snapshot için yeni sürüm üretilebilir.
13. Şirket erişimi korunmaktadır; production'da çapraz şirket katılımcısı yoktur. İşyerleri/şubeler ise eğitimlerde belirtilmemiştir.
14. **Dağılım 5 temel + 15 sektör değildir; 5+5+5+5'tir.**
15. Yeni üretici 20 soruyu zorlar; production'da üç adet 15 soruluk tarihsel snapshot vardır ve DB düzeyinde 20 öğe kısıtı yoktur.

## Doğrulanmış yanlış eşleme örnekleri

- `guzellik_kuafor_spa` → `kimya_kimyasal_uretim`: endüstriyel patlayıcı ortam ekipmanı, yanıcı sıvı transferi ve statik topraklama soruları gelebilir.
- `balikcilik_su_urunleri` → `tarim_ziraat`: traktör devrilmesi, kuyruk mili ve pestisit soruları gelebilir.
- `gemi_insa_tersane` → `kaynakli_imalat`: tersane/denizcilik özgül riskleri dışarıda kalabilir.
- `havalimani_yer_hizmetleri` ve `havacilik` → `depo_lojistik`.
- `cam_seramik` ve `seramik_fayans` → `genel_uretim`.

## RLS ve izolasyon

- `training_sessions`: RLS açık, FORCE RLS ve bir tenant politikası mevcut.
- `training_participants`, soru kapsam/kaynak tabloları ve sınav snapshot alt tabloları: doğrudan RLS yok.
- API şirket erişimi ve join doğrulamaları çapraz şirket katılımcısını engelliyor.
- İşyeri/şube bağlamı zorunlu olmadığı için 36 katılımcının tamamı şube belirtilmemiş eğitimlerde yer alıyor.

## Kök nedenler

1. Kesin NACE ile içerik profilinin aynı alanda saklanması.
2. Eğitim konusu ve süreleri için kalıcı/sürümlü model bulunmaması.
3. Sınav ile sertifikanın aynı onaylı eğitim planı snapshotına bağlanmaması.
4. Soru modelinde alt sektör, risk etiketleri, zorluk, dil ve konu ilişkilerinin yetersiz olması.
5. Kullanıcı PDF yolunun katı soru bankası eşiğini bypass etmesi.
6. Alias benzerliğinin gerçek faaliyet uygunluğu gibi kabul edilmesi.
7. Katılımcı cevap/sonuç zinciri olmadan eğitim düzeyi doğrulama kutularının başarı kanıtı sayılması.
8. Sertifika öncesi merkezi consistency/preflight servisinin bulunmaması.
9. Tarihsel NACE, açıklama, tehlike, konu, süre ve sertifika snapshotlarının bulunmaması.
10. Şube/işyeri bağlamının zorunlu olmaması.

## Kritik engeller

- **BLOCKER-1:** İlgisiz soru ile sınavı tamamlama riski.
- **BLOCKER-2:** Katılım ve başarı kanıtı olmadan sertifika.
- **BLOCKER-3:** Kesin NACE kodunun kaybı.
- **BLOCKER-4:** Eğitim konusu snapshotının bulunmaması.
- **BLOCKER-5:** 5 temel + 15 sektör dağılımının uygulanmaması.
- **BLOCKER-6:** Production soru bankasının tamamen boş olması.

## Korunacak çalışan davranışlar

- Mevcut eğitim ve katılımcı kayıtları
- Tarihsel 15 ve 20 soruluk snapshotlar
- Snapshot soru/cevap bütünlüğü
- Şirket erişim kontrolleri
- Unicode PDF altyapısı
- Mevcut belge görsel düzeni
- Özel eğitim profilleri
- Dört göz soru yayımlama akışı
- Personel ve görevlendirme entegrasyonu

## Faz 2 giriş koşulları

1. Kesin NACE kimliği ile içerik profilini ayırmak.
2. NACE açıklaması, ana sektör, alt sektör, faaliyet grubu, tehlike sınıfı ve risk etiketlerini sürümlü katalog kaydı yapmak.
3. Eğitim planı ve konu sürelerini değişmez snapshot olarak saklamak.
4. Legacy kayıtları silmeden veri durum raporu üretmek.
5. Yeni motoru `5 basic + 15 verified sector/NACE` olarak tasarlamak.
6. Yetersiz havuzda fail-closed davranmak; alias/genel üretimle sessiz tamamlama yapmamak.
7. Sertifika öncesi merkezi tutarlılık raporu oluşturmak.
8. Eski kayıtları `legacy/unverified`, yeni kayıtları katı kurallarla yönetmek.
9. Production dönüşümünden önce staging migration, dry-run ve rollback kanıtı üretmek.

## Faz 1 sonucu

Mevcut sistem yeni kabul kriterlerini karşılamamaktadır. Sorun yalnız soru sayısı değildir; kesin NACE kimliğinin kaybı, konu snapshotı olmaması, geniş fallback, sınav sonucu olmadan sertifika ve 5+15 dağılımının uygulanmaması temel mimari engellerdir.
