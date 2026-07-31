# 15 — Düzeltme Önerileri

**Uygulama durumu:** P0/P1 çekirdek uygulandı; kalan P2 risk kabul.

| Öncelik | Öneri | Durum |
| --- | --- | --- |
| P0 | Rate-limit + SECRET_KEY | **Uygulandı** |
| P1 | İki OSGB IDOR | **Uygulandı** |
| P1 | CA sağlık kısıtı | **Uygulandı** |
| P1 | Upload magic/karantina | **Uygulandı** (`0.9.61`) |
| P1 | Oversight vacuous skor | **Uygulandı** |
| P2 | Tam ClamAV | Risk kabul / sonraki sprint |
| P2 | Lifespan DDL → migration | Risk kabul |
| P2 | Uzun sleep cold + piksel PDF | Risk kabul |
