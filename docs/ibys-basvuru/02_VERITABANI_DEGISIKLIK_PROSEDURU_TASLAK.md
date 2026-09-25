# İBYS — Veritabanı Değişiklik ve Kullanıcı Veri Düzeltme Prosedürü

**Doküman durumu:** Başvuru taslağı / teknik uygulama planı  
**Sürüm:** 1.0-draft  
**Tarih:** 22.09.2026  
**Ürün:** İSG Suite

## 1. Amaç

Bu prosedür; kullanıcılar, işverenler, OSGB yöneticileri veya yetkili İSG profesyonellerinden gelebilecek veri düzeltme/değişiklik taleplerinin veri bütünlüğünü bozmadan, yetki sınırlarını ihlal etmeden, eski/yeni değerleri kaybetmeden ve geriye dönük denetlenebilir biçimde yönetilmesini tanımlar.

## 2. Temel ilkeler

1. Üretim verisi normal iş akışında doğrudan SQL ile değiştirilmez.
2. Her düzeltme kayıt numaralı bir talebe bağlanır.
3. Talebi oluşturan kişi tek başına onaylayıp uygulayamaz (maker-checker).
4. Tenant/firma sınırı her aşamada korunur.
5. Değişiklik öncesi değer, değişiklik sonrası değer, gerekçe, kullanıcı ve zaman kaydedilir.
6. Audit kayıtları silinemez ve içerikleri sonradan değiştirilemez.
7. Sağlık verileri yalnız rol/yetki kapsamına uygun kişilerce düzeltilebilir.
8. Hatalı düzeltme geri alınsa dahi ilk işlem izi silinmez; ters işlem yeni bir olay olarak kaydedilir.
9. Toplu değişiklikler migration/iş emri ve değişiklik planına bağlanır.
10. Acil müdahale normal süreci atlatmaz; "break-glass" olarak ayrıca kayıt ve sonradan inceleme gerektirir.

## 3. Mevcut teknik temel

Kod tabanında şu kontroller mevcuttur:
- `AuditLog` yapısı,
- `old_value` ve `new_value` alanları,
- kullanıcı, firma, aksiyon, entity, IP, modül ve tarih bağlamı,
- PostgreSQL'de append-only koruma,
- `prev_hash/event_hash` SHA-256 hash zinciri,
- DELETE yasağı ve kontrollü FK detach istisnası,
- `audit_chain_verify()` bütünlük kontrolü,
- sağlık kayıtlarında ayrı revizyon/erişim logları,
- risk kayıtlarında revizyon alanları ve değişiklik gerekçesi.

Bu altyapı güçlü bir denetim tabanı sağlar; ancak tüm kullanıcı veri düzeltme taleplerini merkezi olarak yöneten ayrı bir `DataCorrectionRequest` iş akışı henüz doğrulanmamıştır.

## 4. Talep kaydı

Her talep en az şu alanları içermelidir:
- Talep numarası,
- Talep eden kullanıcı/kurum,
- Tenant/OSGB/firma,
- İlgili veri sınıfı/modül,
- Entity tipi ve kayıt ID,
- Düzeltilecek alan(lar),
- Mevcut değer,
- Talep edilen yeni değer,
- Düzeltme gerekçesi,
- Kanıt/doküman referansı,
- Talep tarihi,
- Kişisel veri/hassas sağlık verisi sınıfı,
- Risk seviyesi,
- Durum: pending / under_review / approved / rejected / applied / cancelled,
- İnceleyen,
- Onaylayan,
- Uygulayan,
- Uygulama zamanı,
- İlgili audit event ID/hash.

## 5. İş akışı

### 5.1 Talep
Yetkili kullanıcı uygulama içinden talep oluşturur. Sistem tenant ve kullanıcı bağlamını otomatik ekler.

### 5.2 Ön doğrulama
- Kayıt gerçekten ilgili tenant'a ait mi?
- Talep eden kişinin bu kaydı görmeye ve düzeltme talebi oluşturmaya yetkisi var mı?
- İstenen değişiklik mevzuat/iş kuralına aykırı mı?
- Resmî belge veya açıklama gerekli mi?

### 5.3 İnceleme
İnceleyen yetkili eski/yeni değerleri ve kanıtı kontrol eder. Sağlık verisi ise uygun hekim/sağlık rolü kontrolü ayrıca uygulanır.

### 5.4 Onay
Talebi oluşturan kullanıcı dışında yetkili bir kişi onaylar. Yüksek riskli alanlarda çift onay uygulanabilir.

### 5.5 Uygulama öncesi bütünlük
- İlgili satır/record güncel sürümü yeniden okunur.
- Optimistic lock/version kontrolü yapılır.
- Önceki değer snapshot/hash olarak kaydedilir.
- Talep oluşturulduktan sonra veri değişmişse işlem durdurulur ve yeniden inceleme gerekir.

### 5.6 Uygulama
Değişiklik yalnız servis katmanı üzerinden uygulanır. İşlem tek transaction içinde:
1. Talep durum doğrulaması,
2. Eski değer doğrulaması,
3. Güncelleme,
4. Revision kaydı,
5. Append-only audit kaydı,
6. Talep durumunun `applied` yapılması

adımlarını gerçekleştirir.

### 5.7 Son doğrulama
- Yeni veri okunup talep ile karşılaştırılır.
- İlişkisel bütünlük kontrol edilir.
- İlgili rapor/çıktı etkileniyorsa smoke test yapılır.
- Audit chain doğrulaması planlı periyotta/önemli işlem sonrası çalıştırılır.

## 6. Audit standardı

Her düzeltmede audit kaydı en az:
- actor user id,
- tenant/company id,
- action,
- entity_type,
- entity_id,
- module,
- description,
- old_value,
- new_value,
- reason/ticket number,
- IP/request id,
- created_at

bilgilerini içermelidir.

Audit log üretim PostgreSQL'de append-only ve hash zincirli olmalıdır. Audit kaydı başarısızsa veri değişikliği transaction'ı commit edilmemelidir.

## 7. Doğrudan DB müdahalesi

Normal kullanıcı veri düzeltmelerinde doğrudan production SQL yasaktır.

Zorunlu acil müdahalede:
- Olay/talep numarası,
- Etki analizi,
- Ön yedek,
- İki yetkili onayı,
- Çalıştırılacak SQL/migration'ın kod incelemesi,
- Transaction,
- Etkilenen satır sayısı,
- Önce/sonra kanıtı,
- Audit olayı,
- Sonradan bağımsız inceleme

zorunludur.

## 8. Şema/veritabanı yapısal değişiklikleri

Yapısal değişiklikler yalnız Alembic migration ile:
1. Ayrı branch/PR,
2. Kod incelemesi,
3. Test DB,
4. PostgreSQL parity,
5. Geri dönüş planı,
6. Migration öncesi yedek,
7. CI,
8. Bakım/deploy,
9. Post-deploy doğrulama

adımları ile yapılır.

Production başlangıcı `alembic upgrade head` başarısızsa fail-closed olmalıdır.

## 9. Redaksiyon ve veri minimizasyonu

Audit log gereksiz hassas veri kopyası oluşturmamalıdır. TCKN, sağlık tanısı vb. alanlarda gerektiğinde maskeleme/hash/referans yaklaşımı uygulanır. Düzeltme için zorunlu olmayan belge ve veri sisteme alınmaz.

## 10. Test kriterleri

- Başka tenant kaydı için düzeltme talebi reddedilir.
- Talep eden kendi talebini onaylayamaz.
- Yetkisiz rol sağlık kaydını değiştiremez.
- Eski değer uyuşmazsa işlem durur.
- Audit eklenemezse transaction rollback olur.
- Applied talep ikinci kez uygulanamaz.
- Rejected talep uygulanamaz.
- Audit DELETE/UPDATE reddedilir.
- Audit hash zincirinde tahrifat `audit_chain_verify()` ile tespit edilir.
- Geri alma yeni bir correction/audit olayı üretir; geçmiş kaydı silmez.

## 11. Başvuru kanıtları

- Örnek veri düzeltme talebi ekranı,
- Onay akışı,
- Eski/yeni değer kaydı,
- Audit log ekranı,
- Audit chain `ok=true`,
- İlgili API/test çıktıları,
- Migration/change log örneği,
- Yetki matrisi.

## 12. Teknik geliştirme ihtiyacı

Başvuru öncesinde merkezi `DataCorrectionRequest` modeli + API + yönetim ekranı + test paketi uygulanacaktır. Bu geliştirme mevcut çalışan modülleri değiştirmeden ortak servis katmanı olarak tasarlanmalıdır.
