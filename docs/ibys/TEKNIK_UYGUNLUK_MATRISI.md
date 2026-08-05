# İBYS Başvuru Teknik Uygunluk ve Kanıt Matrisi

> Bu matris başvuru hazırlığı içindir. Bakanlık tescili veya resmî veri sözleşmesine uygunluk beyanı değildir.

| Kontrol alanı | Mevcut durum | Kanıt / bileşen | Başvuru durumu |
|---|---|---|---|
| Çok kiracılı OSGB mimarisi | Her kayıt OSGB/işyeri kapsamında işleniyor | Tenant context, API scope kontrolleri | Hazır |
| Veritabanı tenant izolasyonu | 47 kritik tabloda RLS ve FORCE RLS | Alembic 0074/0075, PostgreSQL davranış testleri | Hazır |
| Rol bazlı yetkilendirme | Global admin ve OSGB admin başvuru API’sine erişebilir | `require_roles`, OSGB scope kontrolü | Hazır |
| Veri-seti kataloğu | 12 aday veri seti tanımlı | `ibys_application_profile.py` | CI bekliyor |
| Alan eşleme matrisi | İç kaynak alanları tanımlı | `FieldMapping.internal_source` | CI bekliyor |
| Resmî veri-seti kodları | Teslim edilmedi | `official_dataset_code=None` | Bakanlıktan bekleniyor |
| Resmî alan adları/türleri | Teslim edilmedi | `official_field=None` | Bakanlıktan bekleniyor |
| Zorunlu alan doğrulaması | Kayıt bazlı eksik alan raporu | `validate_candidate_records` | CI bekliyor |
| Kayıt parmak izi | SHA-256 deterministik fingerprint | `canonical_record_hash` | CI bekliyor |
| Mükerrer gönderim koruması | Kayıt kümesi ve OSGB kapsamına bağlı idempotency | `build_submission_envelope` | CI bekliyor |
| Hassas veri raporlama | Ret raporu içerik yerine fingerprint/alan adı taşır | Gizlilik regresyon testi | CI bekliyor |
| API secret güvenliği | Secret loglara ve yanıtlara yazılmaz | Mevcut integration client politikası | Hazır |
| Timeout ve ağ hata yönetimi | Probe ve gönderim timeout sınıfları mevcut | `ibys_client.py` | Resmî protokole uyarlanacak |
| Kayıt bazlı kabul/ret | Aday profilde mevcut | accepted/rejected listesi | CI bekliyor |
| Bakanlık hata kodu eşlemesi | Resmî katalog yok | Profil uzatma noktası hazır | Bakanlıktan bekleniyor |
| Audit log | Kullanıcı, tarih, OSGB ve entegrasyon işlemi kaydediliyor | IntegrationDryRunLog | Hazır |
| Sağlık verisi şifreleme | Dedicated anahtar ve role dayalı erişim | health field crypto | Hazır |
| Yedek bütünlüğü | SHA-256 checksum ve ZIP preflight | backup integrity katmanı | Hazır |
| Uygulama güvenlik kontrolleri | CORS, header, rate-limit, Redis fallback | Production security release | Hazır |
| Antivirüs zorunluluk kapısı | Fail-closed politika var, gerçek ClamAV bağlı değil | `CLAMAV_REQUIRED` | Altyapı bekliyor |
| Uzak dosya deposu zorunluluk kapısı | Atomik rollback var, gerçek bucket zorunlu değil | `OBJECT_STORAGE_REMOTE_REQUIRED` | Altyapı bekliyor |
| CI/CD | Backend, PostgreSQL, frontend, E2E ve audit | GitHub Actions | Hazır |
| Staging kabul testi | Yeni paket için ayrıca çalıştırılacak | Render staging | Bekliyor |

## Resmî sözleşme geldiğinde yapılacak uyarlama

1. Veri-seti kodlarını `official_dataset_code` alanlarına işlemek.
2. Alan isimleri, veri türleri, uzunluklar ve kod listelerini sürümlü profil olarak eklemek.
3. Bakanlığın kimlik doğrulama yöntemine uygun transport adapteri oluşturmak.
4. İstek/yanıt ve hata kodlarını normalize etmek.
5. Bakanlık test ortamında geçerli, eksik, mükerrer, kısmi kabul ve yetkisiz erişim senaryolarını çalıştırmak.
6. Kabul edilen sözleşme sürümünü değiştirilemez yayın manifestine kaydetmek.

## Başvuru sunumunda kullanılacak doğru ifade

“İSG Suite OSGB; çok kiracılı veri güvenliği, 47 FORCE RLS politikası, sürümlü aday veri-seti profili, kayıt bazlı doğrulama, SHA-256 fingerprint ve idempotency altyapısıyla İBYS entegratör tescil başvurusuna teknik olarak hazırlanmıştır. Resmî veri sözleşmesi ve test erişimi teslim edildiğinde profil uyarlaması ve Bakanlık kabul testleri tamamlanacaktır.”
