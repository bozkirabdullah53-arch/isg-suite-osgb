# ÇSGB İBYS Entegratör Başvurusu — Yol Haritası

**Ürün:** İSG Suite — https://www.isgsuite.tr  
**Kod deposu:** bozkirabdullah53-arch/isg-suite-osgb  
**Hazırlık tarihi:** 22.09.2026  
**Çalışma dalı:** `ibys-basvuru-2026-09-22`

## 1. Amaç

Bu planın amacı Çalışma ve Sosyal Güvenlik Bakanlığı İş Sağlığı ve Güvenliği Genel Müdürlüğüne yapılacak İBYS entegratör/yazılım başvurusu için:

1. Güncel resmî başvuru evrak paketini doğrulamak,
2. İstenen kurumsal prosedürleri gerçek teknik kontrollerle eşleştirmek,
3. Sunum ve canlı demo senaryosunu hazırlamak,
4. Başvuru öncesi teknik boşlukları kapatmak,
5. Başvuru/test aşamasında Bakanlığın vereceği resmî veri sözlüğü, endpoint, profil ve test kodları gelene kadar canlı gönderimi kapalı tutmak,
6. Tüm iddiaları doğrulanabilir kanıtlarla sunmak

için uygulanacaktır.

## 2. Resmî süreçte doğrulanan temel nokta

ÇSGB İSGGM SSS sayfası, entegratör firma olmak isteyen yazılım firmalarının internet sitesindeki başvuru evraklarını hazırlayarak İSGGM'den randevu alıp başvurması gerektiğini belirtir.

Başvuru günü kullanılacak evrak listesi mutlaka İSGGM/İBYS tarafından güncel haliyle yeniden doğrulanacaktır. Eski listeler veya üçüncü taraf örnekleri nihai gereksinim kabul edilmeyecektir.

## 3. Mevcut teknik durum

### Mevcut ve kullanılabilir kanıtlar
- FastAPI + SQLAlchemy + PostgreSQL üretim mimarisi.
- Alembic migration zinciri.
- Tenant/firma izolasyonu ve rol bazlı erişim.
- Sağlık verileri için alan bazlı şifreleme.
- Yedek şifreleme anahtarı desteği.
- `pg_dump` tabanlı veritabanı yedek scripti.
- Firma bazlı yedekleme servisi ve SHA-256 bütünlük kontrolü.
- Audit kayıtlarında eski/yeni değer desteği.
- PostgreSQL'de append-only audit tablosu.
- `prev_hash/event_hash` SHA-256 zinciri ile tahrifat tespiti.
- `audit_chain_verify()` ile zincir doğrulama.
- Request-ID ve erişim logları.
- E-imza orkestrasyon altyapısı ve resmî profil gelene kadar fail-closed entegrasyon kapısı.

### Başvuru öncesi kapatılması gereken boşluklar
1. `WORKPLACE_BACKUPS_ENABLED` ve gece cron'u üretimde şu an kapalıdır.
2. Uzak yedek depolama zorunlu modda değildir.
3. Mevcut yedekleme prosedürü günlük/haftalık/aylık politikayı fiilen devredeymiş gibi anlatmaktadır; teknik gerçekle hizalanmalıdır.
4. Prosedürde referans verilen `backup_restore_drill.py` mevcut kodda doğrulanamamıştır.
5. Kullanıcıların veri düzeltme talepleri için merkezi, kayıt numaralı, onaylı bir **Veri Düzeltme Talebi** iş akışı yoktur.
6. Tüm modüllerde veri düzeltmelerinin aynı maker-checker/audit standardından geçtiğini kanıtlayan kapsamlı test paketi yoktur.
7. Bakanlığın güncel resmî İBYS teknik sözleşmesi/test profili henüz yoktur; gerçek gönderim buna kadar kapalı kalmalıdır.

## 4. Fazlar

### Faz A — Başvuru evrak envanteri
- İSGGM'nin güncel başvuru paketini resmî kaynaktan temin et.
- Evrakları bir kontrol tablosuna aktar.
- Her kalemi: Kurumsal / Hukuki / Teknik / Sunum / Test / Dış bağımlılık şeklinde sınıflandır.
- Sorumlu, hedef tarih, kanıt dosyası ve durum alanı ekle.

**Çıkış kriteri:** Eksik evrak kalemleri tek listede ve güncel resmî kaynağa bağlı.

### Faz B — Veri Yedekleme Prosedürü
- Politika ile fiili üretim konfigürasyonunu hizala.
- Günlük tam DB yedeğini otomatikleştir.
- Yedekleri şifrele ve uzak/ayrı depolamaya kopyala.
- Retention politikasını otomatik uygula.
- Başarı/başarısızlık logu ve alarm üret.
- Restore dry-run + staging geri yükleme tatbikatını kodla.
- Tatbikat kayıtlarını sakla.
- RPO/RTO hedeflerini gerçek test sonucu ile doğrula.

**Çıkış kriteri:** Son başarılı yedek, checksum, uzak kopya ve restore tatbikatı kanıtı gösterilebilir.

### Faz C — Veritabanı Değişiklik / Veri Düzeltme Yönetimi
- `DataCorrectionRequest` kayıt modeli oluştur.
- Talep eden, firma/tenant, kayıt türü/ID, alan, eski değer, istenen yeni değer, gerekçe, kanıt, tarih alanlarını zorunlu yap.
- Talep eden kişi kendi talebini tek başına uygulayamasın.
- Yetkili inceleyen/onaylayan rolü tanımla.
- Uygulama öncesi snapshot/hash üret.
- Uygulama sonrası eski/yeni değerleri append-only audit'e yaz.
- Red/iptal/uygulandı durumlarını kaydet.
- Doğrudan production SQL değişikliğini normal süreçte yasakla.
- Acil "break-glass" prosedürünü çift onay ve sonradan inceleme ile sınırla.
- Sağlık verileri için hekim/yetki kapsamını ayrıca uygula.
- Testler: tenant izolasyonu, yetkisiz düzeltme, kendi kendine onay, audit tahrifatı, rollback.

**Çıkış kriteri:** Bir örnek veri düzeltme talebi baştan sona demo edilebilir ve değişiklik izi sonradan değiştirilemez.

### Faz D — Güvenlik ve operasyonel kanıt
- Audit zinciri: `GET /api/v1/security/audit-chain` sonucu `ok=true`.
- PostgreSQL migration head doğrulaması.
- Şifreleme anahtarlarının secret manager'da olduğunu presence-only kanıtla.
- Yetki/tenant regresyon testlerini çalıştır.
- Dosya yükleme güvenliği, rate limit, TLS, CORS, HSTS kanıtlarını güncelle.
- Yedek ve restore loglarının erişim yetkilerini doğrula.

### Faz E — İBYS veri seti hazırlığı
- Eğitim veri seti alan eşleme tablosu.
- Sağlık gözetimi veri seti alan eşleme tablosu.
- Tehlike kaynağı/risk veri seti alan eşleme tablosu.
- Her alan için: kaynak tablo/kolon, validasyon, zorunluluk, maskeleme/şifreleme, imzalayan rol.
- Resmî Bakanlık şeması geldiğinde adapter contract testleri ekle.
- Gerçek endpoint/profil/test kodu gelmeden production send açma.

### Faz F — Sunum ve canlı demo
- 12–15 slaytlık kurumsal sunum.
- Sunumda yalnız doğrulanmış özellikleri "mevcut" olarak göster.
- Henüz Bakanlık erişimi gerektiren maddeleri "başvuru/test aşamasında etkinleştirilecek" olarak açıkça ayır.
- Canlı demo için anonim/sentetik veri kullan.
- Demo akışı: tenant → personel → eğitim/sağlık/risk → e-imza hazırlığı → yedek → audit → veri düzeltme talebi → audit zinciri doğrulama.

### Faz G — Başvuru dosyası
Başvuru klasörü en az şu gruplarda hazırlanacaktır:
- Kurumsal evraklar,
- Ürün ve teknik mimari,
- Veri Yedekleme Prosedürü,
- Veritabanı Değişiklik Prosedürü,
- Bilgi güvenliği/KVKK dokümanları,
- Sunum,
- Teknik kanıt ekran görüntüleri,
- Test sonuçları,
- E-imza ve entegrasyon hazırlık kanıtları,
- Sürüm ve değişiklik kayıtları.

## 5. Başvuru öncesi "GO / NO-GO" kriteri

Aşağıdaki maddeler tamamlanmadan başvuru sunumunda "tam aktif" denmeyecektir:
- [ ] Günlük otomatik yedek üretimde aktif.
- [ ] Uzak/ayrı yedek kopyası aktif.
- [ ] En az bir başarılı restore tatbikatı kayıtlı.
- [ ] Veri Düzeltme Talebi iş akışı üretimde/testte doğrulanmış.
- [ ] Audit zinciri production PostgreSQL'de `ok=true`.
- [ ] Güncel resmî başvuru evrak listesi doğrulanmış.
- [ ] Sunumdaki tüm ekranlar güncel canlı sürümle uyumlu.
- [ ] Resmî İBYS teknik profil/test erişimi alınana kadar canlı gönderim kapalı.

## 6. İlk uygulanacak işler

1. Veri Yedekleme Prosedürünü teknik gerçekle hizala.
2. Veritabanı Değişiklik Prosedürünü oluştur.
3. Veri Düzeltme Talebi teknik tasarımını çıkar.
4. Yedek restore tatbikatı otomasyonu geliştir.
5. Üretim yedek cron/remote storage pilotunu güvenli şekilde aç.
6. Sunum için kanıt ekranlarını ve demo senaryosunu hazırla.
