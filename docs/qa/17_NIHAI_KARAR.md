# 17 — Nihai QA Kararı

## KABUL — KRİTİK MADDELER KAPALI

İzole smoke, canlı auth/public smoke, UI E2E ve upload/export içerik testleri tamamlandı.

**Kapanan çekirdek:** rate-limit, SECRET_KEY guard, delayed enum, oversight skor, CA sağlık, iki-OSGB IDOR, upload magic+karantina, training verify kod, export PDF/XLSX.

**Risk kabulü ile açık bırakılan:**
- Tam antivirüs motoru (ClamAV)
- Yerel Docker PostgreSQL parity
- Render uzun sleep cold-start
- PDF piksel/görsel tipografi QA
- Alembic dışı lifespan DDL sadeleştirme

**Karar:** Ürün **kritik güvenlik ve izolasyon** açısından canlı kullanıma uygun kabul edilir. Kalan maddeler bloke edici değildir; backlog’a alınabilir.

API hedef sürüm: **0.9.62** (GA OSGB fallback: CRM/finans). Canlıda 0.9.61 doğrulandı; 0.9.62 deploy sonrası marker `ga_osgb_fallback` görünür.

Kalan opsiyonel maddeler: `18_BACKLOG_RISK_KABUL.md`
