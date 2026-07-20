# 11 — Migration ve Yedekleme Değerlendirmesi

| Kontrol | Sonuç | Kanıt / not |
| --- | --- | --- |
| Alembic zinciri | 0001–0013 dosyaları mevcut | Kaynak dizininde 0013 `company_sgk_registry` var |
| QA upgrade | Kısmi geçti | Log 0001→0012’ye kadar başarı gösterir; 0013 sonrası koşu kanıtı yok |
| Temiz SQLite kurulum | Geçti | `alembic upgrade head` exit 0 kaydı |
| PostgreSQL parity | Test edilemedi | Bu turda yalnız SQLite QA kullanıldı |
| `create_all` / lifespan DDL | Drift riski | Alembic ile paralel şema değişimi envanterde tespit edildi |
| Yedek scripti | Mevcut | SQLite copy / `pg_dump` destekleniyor |
| Restore tatbikatı | Test edilemedi | Başarı iddiası yok |
| Upload yedeği | Ayrı değerlendirme gerekir | DB yedeği dosyaları kapsamayabilir |

## Risk

Alembic dışında `create_all` veya uygulama başlangıcındaki `ALTER` işlemleri üretimde migration geçmişi ile gerçek şemayı ayrıştırabilir. Bu, yeni ortam kurulumunda, rollback’te ve PostgreSQL geçişinde beklenmeyen farklılıklara yol açabilir.

## Kabul gereksinimi

Tek migration otoritesi belirlenmeli; boş PostgreSQL üzerinde 0001→0013 upgrade, mevcut veritabanı upgrade, geri dönüş stratejisi ve geri yükleme tatbikatı kanıtlanmalıdır. Yedek kapsamına upload/depo verileri ile sırların yönetimi dahil edilmelidir.
