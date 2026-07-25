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
