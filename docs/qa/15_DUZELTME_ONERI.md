# 15 — Düzeltme Önerileri

**Uygulama durumu:** P0 + sağlık CA kısıtı + oversight skor boşta geçiş kapandı; kalan P1/P2 bekliyor.

| Öncelik | Öneri | Kabul kanıtı | Durum |
| --- | --- | --- | --- |
| P0 | `SimpleRateLimitMiddleware` kaydı + 429 | Tekrarlı isteklerde 429 | **Uygulandı** |
| P0 | Üretimde güçlü `SECRET_KEY` zorunlu | Varsayılanla prod başlangıcı başarısız | **Uygulandı** |
| P1 | Merkezi tenant + iki OSGB IDOR testleri | İzinli/izinsiz HTTP matrisi | **Kısmi** (tek OSGB seed) |
| P1 | Sağlık: CA klinik erişimini kapat | CA 403; hekim/DSP 200 | **Uygulandı** (`0.9.59`) |
| P1 | Upload allowlist / boyut / AV | Traversal + MIME; AV bekliyor | **Kısmi** |
| P1 | Public eğitim verify minimum veri | Geçersiz/geçerli hard PII yok | **Kısmi/OK** |
| P1 | Oversight boşta skor geçişi | Aktivite yok → %0 | **Uygulandı** |
| P2 | Alembic dışı şema mutasyonlarını taşı | PG upgrade/restore | Bekliyor |
| P2 | Cold-start / Failed to fetch | Render ölçüm | Bekliyor |
| P2 | PDF/Excel/UI E2E | Tarayıcı kanıtı | Bekliyor |
