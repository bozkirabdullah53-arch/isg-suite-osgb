# Faz 3 CI Kapsamı

CI aşağıdaki şartları doğrulamalıdır:

- Mevcut SQLite backend testleri bozulmaz.
- PostgreSQL Alembic head ve şema parity bozulmaz.
- Verified NACE snapshot strict modda `genel_uretim` sorusu seçmez.
- İncelenmiş içerik profili kapsamındaki soru seçilir.
- Legacy kayıt geriye uyumlu kalır.
- Özellik bayrağı kapalıyken mevcut davranış korunur.
- Frontend test, lint, build ve E2E smoke değişmeden geçer.
