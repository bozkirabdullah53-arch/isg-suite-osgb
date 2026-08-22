# İSG Suite OSGB — Düzeltme Raporu

**Tarih:** 2026-08-22
**Dal:** `security/a1-critical-hardening`
**Kapsam:** A1 kritik güvenlik maddeleri ve bağımlılık/doğrulama güncellemesi

## Uygulanan düzeltmeler

| Madde | Sonuç | Dosyalar |
| --- | --- | --- |
| A1.1 | Compose PostgreSQL ve backend veritabanı değişkenleri zorunlu ortam değişkenlerine taşındı; sabit parola kaldırıldı. | `docker-compose.yml` |
| A1.2 | Render sağlık alanı şifrelemesi açıldı. | `render.yaml` |
| A1.3 | Render kontrollü yedek geri yükleme özelliği açıldı. | `render.yaml` |
| A1.4 | `python-jose` kaldırıldı; PyJWT 2.10.1'e geçildi. `InvalidTokenError`, `algorithm=ALGORITHM` ve `algorithms=[ALGORITHM]` kullanımı tüm JWT akışlarına uygulandı. | `requirements.txt`, `backend/requirements.txt`, auth/security/middleware/remote-training dosyaları ve JWT testi |
| A1.5 | Her iki backend Docker imajı UID 1000 `appuser` ile çalışacak şekilde sertleştirildi. | `Dockerfile`, `backend/Dockerfile` |
| Bağımlılıklar | Frontend manifesti ve lockfile, lockfile'daki güncel çözümlenmiş sürümlerle senkronlandı. `cryptography` doğrudan bağımlılık olarak korundu. | `frontend/package.json`, `frontend/package-lock.json` |
| Regresyon sertleştirmesi | Lifecycle v2 content guard wrapper'ları yeniden kurulurken callable zincirinde recursion oluşması engellendi; test fixture'ları güncel aktif görevlendirme, katalog ve OSGB yönetici sözleşmelerine hizalandı. | `backend/app/services/training_lifecycle_v2_content_guards.py`, ilgili backend testleri |
| Dokümantasyon | Kurulum, üretim kontrolü ve düzeltme raporu güncellendi. | `README.md`, `PRODUCTION_CHECKLIST.md`, `backend/scripts/restore_database.md`, bu dosya |

## Kontroller

- Python kodu ve bağımlılık manifestlerinde `python-jose`, `from jose` ve `JWTError` araması: sonuç yok; dokümantasyonda geçiş bilgisi olarak anılıyor.
- JWT `encode` çağrıları `algorithm=ALGORITHM`; `decode` çağrıları `algorithms=[ALGORITHM]` kullanıyor.
- Backend tam regresyon: **907 başarılı, 8 atlandı**; yalnızca duplicate ZIP girdisi için beklenen 1 uyarı üretildi.
- Backend hedef güvenlik testleri: **40 başarılı**.
- Frontend testleri: **116 başarılı**.
- Personel/OSGB doğrulama kapısı: **17 başarılı**.
- Frontend Vite üretim derlemesi: **başarılı**; mevcut ESLint uyarıları hata değil.
- `npm ci --ignore-scripts --no-audit --no-fund`: **başarılı**.
- `docker-compose.yml` ve `render.yaml`: **YAML ayrıştırması başarılı**.
- `docker compose config --quiet`: ortamda Docker CLI bulunmadığı için çalıştırılamadı.

## Yayın öncesi operasyonel şartlar

- Render Dashboard'da `HEALTH_FIELD_ENCRYPTION_KEY` ve `BACKUP_ENCRYPTION_KEY` gizli değerleri tanımlanmalı.
- `BACKUP_RESTORE_ENABLED=true` canlı geri yükleme yetkisi verir; önce staging dry-run ve geri yükleme testi tamamlanmalı, gerçek yazma yalnız `confirm=RESTORE` ile yapılmalı.
- Docker Compose için `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL` ve `SECRET_KEY` değerleri `.env` veya çalışma ortamında sağlanmalı.
- Üretim ortamında Node sürümü `frontend/package.json` motor kuralına uygun olarak 20.x olmalı; doğrulama ortamında Node 24 ile yalnızca engine uyarısı alındı.
