# 13 — Önceliklendirilmiş Bulgu Listesi

**Güncelleme:** 2026-07-20 son tur (upload magic + export + latency)

| ID | Öncelik | Bulgu | Durum |
| --- | --- | --- | --- |
| F-01 | P0 | Rate-limit kaydı | **KAPANDI** |
| F-02 | P0 | SECRET_KEY prod guard | **KAPANDI** |
| F-03 | P1 | İki OSGB IDOR | **KAPANDI** |
| F-04 | P1 | CA sağlık erişimi | **KAPANDI** |
| F-05 | P1 | Upload güvenlik | **KAPANDI (çekirdek)** — magic-byte + karantina; tam AV motoru yok |
| F-06 | P1 | Eğitim verify PII | **KAPANDI / kabul** |
| F-07 | P2 | Alembic/lifespan DDL drift | **Açık — risk kabul** (canlı heal + migration 0014) |
| F-08 | P2 | Cold-start Failed to fetch | **Kısmi/kabul** — warm/auth OK; uzun sleep ölçülmedi |
| F-09 | P2 | PDF/Excel görsel | **Kısmi/kabul** — magic/MIME/bytes OK; piksel QA yok |
| F-10 | P3 | Yerel Docker PG | **Engelli/kabul** — makinede docker yok; canlı PG OK |
| F-11 | P1 | Oversight vacuous skor | **KAPANDI** |
| F-12 | P0 | delayed enum | **KAPANDI** |
| F-13 | P2 | training verify UNIQUE 500 | **KAPANDI** |

P0/P1 çekirdek kapalı. Kalan P2/P3 risk kabulü ile kapatıldı.
