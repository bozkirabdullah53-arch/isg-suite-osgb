# NACE Eğitim Sunumu — Production Live Activation Evidence

Tarih: 2026-08-09

## Kapsam

Production API üzerinde aşağıdaki feature flag'ler açık ve force-off bayrakları kapalı olacak şekilde doğrulandı:

- `NACE_TRAINING_PRESENTATION_ENABLED=true`
- `NACE_TRAINING_PRESENTATION_FORCE_OFF=false`
- `NACE_TRAINING_PRESENTATION_PILOT_COMPANY_IDS=118`
- `NACE_TRAINING_PRESENTATION_TRACEABILITY_ENABLED=true`
- `NACE_TRAINING_PRESENTATION_TRACEABILITY_FORCE_OFF=false`
- `NACE_TRAINING_PRESENTATION_COVERAGE_V2_ENABLED=true`
- `NACE_TRAINING_PRESENTATION_COVERAGE_V2_FORCE_OFF=false`

Production veritabanında bu tarihte tek şirket kaydı vardır (`company_id=118`); dolayısıyla mevcut tüm production tenant kapsamı etkinleştirilmiştir. Gelecekte eklenecek yeni tenant'lar mevcut fail-closed allowlist davranışı nedeniyle otomatik olarak etkinleşmez.

## Deploy

- Git commit: `08caf6598bcdd3b5ea09bcc0d9a48ccd2d703ad9`
- Render production API deploy: `dep-d9rslf0n74is73fg9l40`
- Durum: `live`
- Build: successful
- Migrations: OK
- Application startup: complete
- Uvicorn: `0.0.0.0:10000`
- `/health`: HTTP 200
- Aktivasyon penceresinde `error` veya `warning` logu: yok

## Veri bütünlüğü

Aktivasyon öncesi ve sonrası sayımlar aynıdır:

- Alembic head: `0083_profile_osgb_scope`
- Companies: `1`
- NACE snapshots: `7`
- Presentation versions: `3`
- Presentation approvals: `1`

Aktivasyon sırasında yeni sunum, sınav, sertifika, katılım veya tarihsel kayıt otomatik oluşturulmamış / yeniden yazılmamıştır.

## Rollback

Acil durumda katmanlar ayrı ayrı fail-closed kapatılabilir:

- `NACE_TRAINING_PRESENTATION_FORCE_OFF=true`
- `NACE_TRAINING_PRESENTATION_TRACEABILITY_FORCE_OFF=true`
- `NACE_TRAINING_PRESENTATION_COVERAGE_V2_FORCE_OFF=true`
