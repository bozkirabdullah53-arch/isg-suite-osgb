# 17 — Nihai QA Kararı

## TEKRAR TEST TAMAMLAMA (0.9.60)

İzole + canlı temel kanıt seti tamamlandı.

**Bu turda kapanan:**
- F-03 iki-OSGB çapraz IDOR (seed + 403)
- F-13 eğitim verification_code UNIQUE → 500
- Export XLSX/PDF content-type smoke

**Hâlâ opsiyonel / kabul riski:**
- Upload AV/karantina
- Yerel PostgreSQL Docker parity
- PDF görsel kalite, mobil E2E
- Render uzun sleep cold-start

**Karar:** Kritik P0/P1 çekirdek maddeleri kapalı. Kalanlar ürün kabulünü bloke etmez; sonraki sprint / risk kabulü.
