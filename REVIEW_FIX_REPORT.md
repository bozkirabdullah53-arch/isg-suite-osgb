# İSG Suite OSGB — Düzeltme Raporu

**Tarih:** 2026-08-22
**Dal:** `security/a1-critical-hardening`
**Kapsam:** A1 kritik güvenlik maddeleri, backend/frontend güvenlik denetimi ve bağımlılık/doğrulama güncellemesi

## Uygulanan düzeltmeler

| Madde | Sonuç | Dosyalar |
| --- | --- | --- |
| A1.1 | Compose PostgreSQL ve backend veritabanı değişkenleri zorunlu ortam değişkenlerine taşındı; sabit parola kaldırıldı. | `docker-compose.yml` |
| A1.2 | Render sağlık alanı şifrelemesi açıldı. | `render.yaml` |
| A1.3 | Render kontrollü yedek geri yükleme özelliği açıldı. | `render.yaml` |
| A1.4 | `python-jose` kaldırıldı; PyJWT 2.10.1'e geçildi. `InvalidTokenError`, `algorithm=ALGORITHM` ve `algorithms=[ALGORITHM]` kullanımı tüm JWT akışlarına uygulandı. | `requirements.txt`, `backend/requirements.txt`, auth/security/middleware/remote-training dosyaları ve JWT testi |
| A1.5 | Her iki backend Docker imajı UID 1000 `appuser` ile çalışacak şekilde sertleştirildi. | `Dockerfile`, `backend/Dockerfile` |
| P1-07 | Sistem sağlık, altyapı ayrıntısı ve asenkron iş durumu cevapları yetkisiz erişime kapatıldı; public liveness cevabı minimal bırakıldı. | `backend/app/api/system.py`, `backend/app/services/release_status.py` |
| P1-09 | Parola sıfırlama belirteçleri eskisini geçersizleştirir ve tüketim sırasında satır kilidiyle tek kullanımlıdır. | `backend/app/services/auth_security.py` |
| P1-10 | Production PostgreSQL/HTTPS yapılandırması, CORS origin doğrulaması ve refresh cookie SameSite politikası sıkılaştırıldı. | `backend/app/core/config.py`, `backend/app/core/cors_policy.py`, `backend/app/core/auth_cookies.py` |
| P1-11 | Access token kalıcı `localStorage` yerine bellek/`sessionStorage` oturum yardımcılarına taşındı; eski değerler güvenli biçimde migrate edilir. | `frontend/src/auth_session.js`, frontend API ve ekran dosyaları |
| P1-12 | İndirme dosya adları header injection/path bileşeni açısından normalize edildi; `pg_dump` veritabanı parolasını process argümanlarına koymaz. | `backend/app/services/stored_files.py`, `backend/scripts/backup_database.py` |
| Bağımlılıklar | Backend manifestleri eşitlendi; PyJWT, `python-pptx` ve `holidays` sürümleri root/backend listelerinde hizalandı. Frontend manifesti ve lockfile senkron tutuldu. | `requirements.txt`, `backend/requirements.txt`, `frontend/package.json`, `frontend/package-lock.json` |
| Regresyon sertleştirmesi | Lifecycle v2 content guard wrapper'ları yeniden kurulurken callable zincirinde recursion oluşması engellendi; test fixture'ları güncel aktif görevlendirme, katalog ve OSGB yönetici sözleşmelerine hizalandı. | `backend/app/services/training_lifecycle_v2_content_guards.py`, ilgili backend testleri |
| Dokümantasyon | Kurulum, üretim kontrolü ve düzeltme raporu güncellendi. | `README.md`, `PRODUCTION_CHECKLIST.md`, `backend/scripts/restore_database.md`, bu dosya |

## Kontroller

- Python kodu ve bağımlılık manifestlerinde `python-jose`, `from jose` ve `JWTError` araması: sonuç yok; dokümantasyonda geçiş bilgisi olarak anılıyor.
- JWT `encode` çağrıları `algorithm=ALGORITHM`; `decode` çağrıları `algorithms=[ALGORITHM]` kullanıyor.
- Frontend kaynaklarında access/MFA token için doğrudan `localStorage` kullanımı kaldırıldı; yalnızca geriye dönük tek seferlik migration ve refresh-cookie modu bayrağı kaldı.
- Production config PostgreSQL ve tam HTTPS origin'i zorunlu kılar; public health payload'ı feature flag/altyapı ayrıntısı döndürmez.
- Backend tam regresyon: **912 başarılı, 8 atlandı**; yalnızca duplicate ZIP girdisi için beklenen 1 uyarı üretildi.
- Backend hedef güvenlik testleri: **25 başarılı**; auth/job/token hedefleri ayrıca **11 başarılı**.
- Frontend Vitest testleri: **117 başarılı**.
- Frontend bağımlılık güvenlik taraması: **yüksek önem seviyesinde 0 açık**.
- Frontend Vite üretim derlemesi: **başarılı**; mevcut ESLint uyarıları hata değil.
- `npm ci --ignore-scripts --no-audit --no-fund`: **başarılı**.
- `docker-compose.yml` ve `render.yaml`: **YAML ayrıştırması başarılı**.
- `docker compose config --quiet`: ortamda Docker CLI bulunmadığı için çalıştırılamadı.

## Yayın öncesi operasyonel şartlar

- Render Dashboard'da `HEALTH_FIELD_ENCRYPTION_KEY` ve `BACKUP_ENCRYPTION_KEY` gizli değerleri tanımlanmalı.
- `BACKUP_RESTORE_ENABLED=true` canlı geri yükleme yetkisi verir; önce staging dry-run ve geri yükleme testi tamamlanmalı, gerçek yazma yalnız `confirm=RESTORE` ile yapılmalı.
- Docker Compose için `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL` ve `SECRET_KEY` değerleri `.env` veya çalışma ortamında sağlanmalı.
- Üretim ortamında Node sürümü `frontend/package.json` motor kuralına uygun olarak 20.x olmalı; doğrulama ortamında Node 24 ile yalnızca engine uyarısı alındı.

## Entegrasyon durumu

İBYS ve İSG-KATİP için resmi teknik sözleşme, sandbox ve erişim bilgileri repository'de bulunmadığından gerçek endpoint veya veri formatı uydurulmadı. Mevcut adapter, probe ve dry-run akışları korunur; canlı gönderim için resmi sözleşme, secret yönetimi ve contract testleri tamamlanmalıdır.
