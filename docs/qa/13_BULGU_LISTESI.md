# 13 — Önceliklendirilmiş Bulgu Listesi

**Not:** Bu raporlama turunda düzeltme uygulanmadı.

| ID | Öncelik | Bulgu | Kanıt / durum |
| --- | --- | --- | --- |
| F-01 | P0 | Rate-limit middleware `main.py` içine kayıtlı değil | Kod envanteri bulgusu; doğrulama ve düzeltme bekliyor |
| F-02 | P0 | Üretimde varsayılan `SECRET_KEY` kullanım riski | Kodda varsayılan değer; canlı yapılandırma görülmedi |
| F-03 | P1 | Tenant izolasyonu tüm router/iki OSGB ile kanıtlanmadı | Tek CA→diğer firma personel vakası 403; kapsam eksik |
| F-04 | P1 | Sağlık PII/CA ve alan bazlı gizlilik doğrulanmadı | Uzman 403, hekim 200; CA/export/tekil kayıt test edilmedi |
| F-05 | P1 | Upload AV, traversal, içerik doğrulama ve indirme yetkisi test edilmedi | Dosya uçları mevcut; güvenlik kanıtı yok |
| F-06 | P1 | Public eğitim verify gerçek kodda PII sızdırma riski | Geçersiz kod 200/`valid:false`; gerçek belge senaryosu yok |
| F-07 | P2 | Alembic ile `create_all`/lifespan DDL drift riski | Paralel şema yönetimi gözlemi |
| F-08 | P2 | Render cold-start / “Failed to fetch” kök nedeni doğrulanmadı | QA iş kuralı başarılı; canlı katman test edilmedi |
| F-09 | P2 | PDF/Excel ve UI E2E kalite kapsamı yok | Endpoint/build varlığı yeterli değil |
| F-10 | P3 | Docker Compose ve PostgreSQL parity çalıştırılmadı | İzole test yalnız SQLite |

P0 bulguları, canlı konfigürasyonu veya middleware kaydıyla çürütülmeden kabul edilemez. P1 bulguları kişisel sağlık verisi ve tenant sınırı içerdiği için canlıya geçiş öncesi kapatılmalı ya da risk sahibi tarafından açıkça kabul edilmelidir.
