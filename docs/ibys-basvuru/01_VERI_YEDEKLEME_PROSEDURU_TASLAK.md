# İBYS — Veri Yedekleme ve Geri Yükleme Prosedürü

**Doküman durumu:** Başvuru taslağı / teknik doğrulama sürümü  
**Sürüm:** 1.1-draft  
**Tarih:** 22.09.2026  
**Ürün:** İSG Suite  
**Alan adı:** https://www.isgsuite.tr

## 1. Amaç

Bu prosedür, İSG Suite üzerinde işlenen İSG verilerinin kayıp, bozulma, yetkisiz değişiklik, altyapı arızası ve insan hatası senaryolarına karşı geriye dönük olarak güvenli biçimde yedeklenmesi, bütünlüğünün doğrulanması, saklanması ve gerektiğinde kontrollü geri yüklenmesi için uygulanacak kuralları tanımlar.

## 2. Kapsam

- PostgreSQL üretim veritabanı,
- Uygulama tarafından yüklenen doküman ve ekler,
- Firma/tenant bazlı taşınabilir yedek paketleri,
- Sağlık ve kimlik gibi şifreli hassas alanlar,
- Yedekleme metadata, checksum ve işlem logları.

Parola, token, secret key veya oturum belirteçleri taşınabilir kullanıcı yedek paketlerine dahil edilmez.

## 3. Sorumluluklar

| Rol | Sorumluluk |
|---|---|
| Sistem yöneticisi | Yedek görevleri, alarm, saklama, restore tatbikatı |
| Bilgi güvenliği sorumlusu | Şifreleme, erişim, anahtar yönetimi, denetim |
| Uygulama yöneticisi | Tenant kapsamı ve işlevsel doğrulama |
| Veri sahibi/yetkili kullanıcı | Geri yükleme/düzeltme talebinin iş gerekçesi |
| Onaylayan yetkili | Geri yükleme öncesi bağımsız onay |

## 4. Yedekleme ilkeleri

1. Üretim veritabanı için en az günlük tam yedek alınır.
2. Yedek aynı fiziksel/lojik hata alanında tek kopya olarak tutulmaz.
3. Yedek dosyası saklama alanına çıkmadan önce şifrelenir veya şifreli depoda tutulur.
4. Her yedek için SHA-256 veya eşdeğer bütünlük kanıtı tutulur.
5. Yedekleme başarısızlığı sessizce geçilemez; alarm ve olay kaydı oluşturulur.
6. Saklama süresi otomatik politika ile uygulanır.
7. Geri yükleme doğrudan production'a ilk adım olarak uygulanmaz; önce staging/dry-run yapılır.
8. Geri yükleme işlemi yetkili ve izlenebilir kullanıcı tarafından yapılır, audit log'a yazılır.

## 5. Mevcut teknik kontroller

Kod tabanında:
- `backend/scripts/backup_database.py`: PostgreSQL için `pg_dump --format=custom`.
- DB parolası process argümanına yazılmaz; `PGPASSWORD` ile geçirilir.
- `BACKUP_ENCRYPTION_KEY` mevcutsa dump Fernet ile şifrelenir ve ham dump silinir.
- `workplace_backup.py`: tenant/firma bazlı yedek paketi.
- `backup_safety.py`: ZIP güvenliği ve bütünlük kontrolleri.
- Uzak kopya için object storage altyapısı ve fail-closed seçeneği mevcuttur.
- Geri yükleme production'da `BACKUP_RESTORE_ENABLED=false` ile varsayılan kapalıdır.

## 6. Üretim politikası

Hedef üretim politikası:
- Günlük tam DB yedeği: her gece.
- Son 30 günlük günlük yedekler.
- Haftalık seçilmiş kopyalar: 12 hafta.
- Aylık seçilmiş kopyalar: 12 ay.
- Kritik sürüm/migration öncesi ek yedek.
- Dosya/object storage için versiyonlama veya ayrı snapshot politikası.
- Tenant taşınabilir yedekleri için ürün politikasına göre saklama.

Bu değerler başvuru öncesinde gerçek altyapı konfigürasyonu ve maliyet/kapasite ile doğrulanacak; sunumda yalnız fiilen etkin değerler kullanılacaktır.

## 7. Şifreleme ve anahtar yönetimi

- Yedek şifreleme anahtarı kaynak kodda tutulmaz.
- `BACKUP_ENCRYPTION_KEY` yalnız secret manager/Render secret olarak saklanır.
- Sağlık verileri uygulama veritabanında ayrıca alan bazlı şifrelenir.
- Anahtar erişimleri en az yetki prensibine göre sınırlandırılır.
- Anahtar değişimi/rotasyonu ayrı kontrollü işlem olarak loglanır.

## 8. Otomatik yedek akışı

1. Zamanlanmış görev tetiklenir.
2. DB bağlantısı ve yeterli disk/uzak depolama kontrol edilir.
3. `pg_dump` üretilir.
4. Şifreleme uygulanır.
5. SHA-256/checksum üretilir.
6. Uzak/ayrı depolamaya kopyalanır.
7. Uzak kopyanın boyut/checksum doğrulaması yapılır.
8. Yedek metadata kaydı "completed" durumuna alınır.
9. Hata halinde "failed" kaydı + alarm oluşturulur.
10. Retention temizliği yalnız doğrulanmış yeni yedekten sonra uygulanır.

## 9. Geri yükleme

1. Kayıt numaralı geri yükleme talebi oluşturulur.
2. Kapsam, tarih, hedef ve gerekçe belirlenir.
3. Yetkili ikinci kişi onayı alınır.
4. İlgili yedeğin checksum bütünlüğü doğrulanır.
5. Yedek staging ortamına açılır.
6. Migration sürümü, satır sayıları, tenant kapsamı ve kritik ilişkiler doğrulanır.
7. Uygulama smoke testleri yapılır.
8. Production bakım penceresi açılır.
9. `BACKUP_RESTORE_ENABLED` sadece işlem süresince kontrollü açılır.
10. Restore uygulanır.
11. Sonrasında kullanıcı/tenant, sağlık şifreleme ve audit zinciri kontrol edilir.
12. Restore özelliği tekrar kapatılır.
13. İşlem raporu ve audit kaydı saklanır.

## 10. Restore tatbikatı

- En az aylık.
- Büyük migration/sürüm öncesi ek tatbikat.
- Gerçek kişisel veri içeren üretim yedeği kullanılıyorsa staging erişimi sınırlandırılır.
- Tatbikat sonucu: yedek ID, tarih, checksum, restore süresi, doğrulama sonuçları, RPO/RTO, hata/aksiyon alanlarıyla kayıt altına alınır.

## 11. RPO/RTO

Başvuru dosyasında RPO/RTO hedefleri ancak gerçek restore tatbikatı ile doğrulandıktan sonra kesin değer olarak yayınlanacaktır.

Başlangıç hedefi:
- RPO: 24 saat veya daha iyi.
- RTO: 4 saat veya daha iyi.

## 12. Denetim kanıtları

Başvuruda aşağıdaki kanıtlar sunulacaktır:
- Son başarılı otomatik yedek kaydı,
- Uzak kopya doğrulaması,
- Şifreleme/secret presence kanıtı,
- Checksum doğrulaması,
- Restore tatbikat raporu,
- Retention kayıtları,
- Yedek/restore yetki matrisi,
- İlgili audit log kayıtları.

## 13. Mevcut açık maddeler

22.09.2026 itibarıyla:
- `WORKPLACE_BACKUPS_ENABLED=false`.
- Gece workplace backup cron'u da kapalı.
- Remote workplace backup özelliği kapalı.
- Dokümanda daha önce referans verilen `backup_restore_drill.py` kod tabanında doğrulanamadı.

Bu maddeler kapatılmadan "otomatik yedekleme prosedürü üretimde tam aktif" beyanı yapılmayacaktır.
