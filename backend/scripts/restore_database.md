# Veritabanı Geri Yükleme

## SQLite

1. Uygulamayı durdurun.
2. Mevcut `isgsuite.db` dosyasını ayrıca saklayın.
3. Yedek `.db` dosyasını uygulamanın veritabanı yolu üzerine kopyalayın.
4. Uygulamayı başlatın ve sağlık kontrolünü çalıştırın.

## PostgreSQL

```bash
createdb isgsuite_restore
pg_restore --clean --if-exists --no-owner \
  --dbname=isgsuite_restore backups/isgsuite-YYYYMMDD-HHMMSS.dump
```

Canlı veritabanına geri yüklemeden önce ayrı bir test veritabanında doğrulama yapın.

# Tenant arşiv (API) — restore-plan vs restore

- `GET /api/v1/archives/{id}/restore-plan` — salt okunur inceleme (`inspect_backup_file`). Canlı veriyi değiştirmez.
- `POST /api/v1/archives/{id}/restore` with `dry_run=true` — dosya yolu eşlemesini listeler (yazmaz); flag gerekmez.
- `POST .../restore` with `dry_run=false` — **kapalı** (`BACKUP_RESTORE_ENABLED=false`) + `confirm=RESTORE`.
- Tenant ZIP arşivi satır satır tüm DB domain'ini geri kurmaz; object/manifest odaklıdır. Tam DB restore için yukarıdaki `pg_restore` / SQLite adımlarını kullanın.

## %100 cutover (Render env — Dashboard)

Blueprint sync yetmezse API Environment'ta elle:

1. `ASYNC_JOBS_FORCE_OFF=false`, `ASYNC_JOBS_ENABLED=true` (Redis zaten var)
2. `UPLOAD_GATEWAY_ENABLED=true`
3. Cloudflare R2 → bucket + API token → doldur:
   - `OBJECT_STORAGE_BUCKET`
   - `OBJECT_STORAGE_ACCESS_KEY` / `OBJECT_STORAGE_SECRET_KEY`
   - `OBJECT_STORAGE_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
   - `OBJECT_STORAGE_REGION=auto`
4. Probe: `GET /api/v1/system/storage-probe` (global_admin) → `reachable`
5. Sonra `OBJECT_STORAGE_BACKEND=r2` (local'den çık)
6. Opsiyonel: `HEALTH_FIELD_ENCRYPTION_KEY` (32+ char) sonra `HEALTH_FIELD_ENCRYPTION_ENABLED=true`
7. `BACKUP_RESTORE_ENABLED` yalnız staging restore drill sonrası
