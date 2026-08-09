# İSG SUITE — İBYS / İSBS-e‑Reçete Başvuru Hazırlık Durum Raporu

**Tarih:** 09.08.2026  
**Kaynak:** Production PostgreSQL üzerinde salt-okunur preflight + source-code/CI incelemesi.  
**Uyarı:** Bu rapor Bakanlık tescil/onay belgesi değildir; başvuru öncesi eksik yönetim raporudur.

## 1. Bugünkü teknik durum

- Production Alembic başlangıç seviyesi: `0083_profile_osgb_scope`.
- Başvuru dalında yeni hedef: `0084_regulatory_identity_vault`.
- Ayrı Regulatory Application Readiness CI üzerinde clean PostgreSQL migration, vault şeması ve fail-closed/crypto test kapısı tanımlandı.
- Legacy generic İBYS adapter resmî entegrasyon olarak kabul edilmemektedir.
- ÇSGB veya Sağlık Bakanlığı tarafından verilen resmî profil/test kodu bulunmadan formal send kapalıdır.
- Resmî TCKN/YKN ihtiyacı için mevcut `Employee` çekirdeğini değiştirmeyen ayrı şifreli identity vault tasarlanmıştır.

## 2. Production veri preflight — 09.08.2026

### Aktif işyerleri

| ID | İşyeri | Tehlike sınıfı | SGK sicil | NACE |
|---:|---|---|---|---|
| 119 | İŞEYERİBİR | Az Tehlikeli | Mevcut | **Eksik** |
| 120 | İŞEYERİİKİ | Tehlikeli | Mevcut | **Eksik** |
| 121 | İŞEYERİÜÇ | Çok Tehlikeli | Mevcut | **Eksik** |

**P0 veri hazırlığı:** 3/3 aktif işyerinin NACE kodu boş. Resmî veri sözlüğü/test senaryosundan önce gerçek faaliyet kodları işletme belgelerinden doğrulanarak sisteme girilmelidir. NACE tahmin edilmemelidir.

### Çalışan / kimlik

- Aktif Employee: **0**
- Aktif çalışanlarda legacy alanda tam 10/11 haneli kimlik gibi görünen değer: **0**
- Bu nedenle bugünkü production verisinde taşınacak aktif TCKN bulunmamaktadır.
- Gelecekte resmî entegrasyon kimliği `RegulatoryIdentity` vault üzerinden alınacaktır; genel Employee API'sine plaintext TCKN eklenmeyecektir.

### İşyeri hekimi

- Aktif işyeri hekimi: **3**
- Sertifika numarası eksik aktif işyeri hekimi: **0**

### Reçete

- Reçete toplamı: **0**
- READY: **0**
- APPROVED: **0**

**Test hazırlığı:** Bakanlığın resmî test profili/test kişileri teslim edilince gerçek production çalışan verisi kullanılmadan sentetik/kurumca verilen test senaryosu oluşturulmalıdır.

## 3. Yazılım tarafında kapatılan / kapatılmakta olan başvuru riskleri

1. Resmî onay ile generic API erişiminin karıştırılması → **Fail-closed authority gate**.
2. Secret/test kodunun status/log çıktısına sızması → **presence-only readiness**.
3. Duplicate/tekrar gönderimde belirsizlik → **canonical hash + idempotency key**.
4. Resmî kimliğin genel personel tablosunda plaintext tutulması riski → **ayrı şifreli Regulatory Identity Vault**.
5. Clean PostgreSQL kurulumunda 0083 legacy constraint varsayımı → **defensive migration uyumluluğu**.
6. Başvuru/testte hangi kontrolün nerede olduğu belirsizliği → **Technical Evidence Map**.
7. Bakanlık test senaryolarının plansız yürütülmesi → **Authority Test Plan**.

## 4. Yazılımla kapatılamayan başvuru kalemleri

### ÇSGB İBYS

- Güncel İBYS/İSGGM başvuru evrak setinin başvuru günü resmî kaynaktan alınması/doğrulanması.
- Evrakların yetkili imza/kaşe ile tamamlanması.
- İSGGM randevusu.
- Bakanlıkça verilecek güncel veri sözlüğü, test profili, endpoint ve test erişim bilgileri.
- Test kabulü sonrası tescil/entegratör numarası.

### Sağlık Bakanlığı KTS / İSBS

- Kuruluş ve güncel Ticaret Sicil Gazetesi.
- SGK işyeri tescil belgesi.
- Son üç yıla ait kılavuz şartlarını karşılayan bilançolar.
- SBYS Yetkili Belgesi.
- SBYS Yazılım Listesinde İSBS ürün kaydı.
- TÜRKAK kapsam şartını sağlayan TS ISO/IEC 27001 belgesi.
- SPICE en az Seviye 2 veya CMMI en az Seviye 3 belgesi.
- Gizlilik sözleşmesi ve firma yönetici/yetkili/personel bilgileri.
- Gerekliyse vekâletname.
- Ön kayıt sonrası Bakanlıkça verilecek yazılım erişim test kodu ve test kılavuzu.
- Test kabulü sonrası production yazılım erişim kodu/KTS kayıt süreci.

## 5. Başvuru öncesi GO kriteri

İSG SUITE yazılım release'i başvuru/test sunumuna ancak aşağıdaki durumda **GO** kabul edilmelidir:

- Regulatory Application Readiness CI = GREEN
- Clean PostgreSQL migration = GREEN
- PostgreSQL schema parity = GREEN
- Formal send gate = test/prod varsayılan kapalı
- Production NACE veri eksikleri = 0
- Testte kullanılacak resmî/sentetik kimlikler yalnız encrypted vault'ta
- Kurumsal belge checklist'i eksiksiz
- Bakanlık güncel test profil sürümü arşivlenmiş
- Test sonuçları release SHA ile eşleştirilmiş

Bu şartlardan biri eksikse başvuru dosyası hazırlanabilir; fakat teknik test/production entegrasyonu “hazır/onaylı” olarak beyan edilmemelidir.
