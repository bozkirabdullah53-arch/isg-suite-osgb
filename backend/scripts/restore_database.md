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
