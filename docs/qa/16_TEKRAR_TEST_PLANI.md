# 16 — Tekrar Test Planı

**Başlatma koşulu:** Aşama 8 düzeltmeleri onaylanıp uygulanmış olmalıdır. Canlıya yazmadan önce izole QA ve PostgreSQL benzeri ortam kullanılır.

**Son koşum:** 2026-07-20 — `scripts/qa_retest_smoke.py` + pytest + api/security smoke (izole SQLite).

| Sıra | Alan | Tekrar test | Başarı ölçütü | Durum |
| ---: | --- | --- | --- | --- |
| 1 | Konfigürasyon | Varsayılan `SECRET_KEY` ile prod mod başlatma; güçlü sırla login | Güvensiz başlatma engellenir | ✅ Geçti (`qa-retest-smoke` + `test_security_config`) |
| 2 | Rate limit | Login ve hassas endpointlerde sınır aşımı | 429, doğru reset ve kullanıcı dostu hata | ✅ Geçti (middleware kayıtlı; birim testte limit=3 → 429) |
| 3 | Tenant | İki OSGB, üç firma, tüm rol/nesne kombinasyonları | Yetkisiz tüm istekler 403/404; izinli istekler başarılı | ⚠️ Kısmi — aynı OSGB firma-arası IDOR 403; **iki OSGB seed yok** (F-03) |
| 4 | Sağlık | Uzman, CA, hekim, DSP, readonly; liste/tekil/export | Klinik/konfidansiyel alanlar yalnız yetkili rolde | ✅ Geçti — CA/uzman/readonly 403; hekim/DSP 200; CA export 403 (`0.9.59`) |
| 5 | Dosya | Traversal, MIME, boyut, malware simülasyonu, yetkisiz indirme | Reddedilir/karantinaya alınır; veri sızmaz | ⚠️ Kısmi — traversal + kötü MIME 400; AV/karantina yok (F-05) |
| 6 | Eğitim verify | Geçerli/geçersiz kod ve yanıt PII incelemesi | Yalnız onaylı minimum veri döner | ✅ Geçti — geçersiz minimal; geçerli kodda hard PII yok |
| 7 | Migration | Boş ve veri içeren PostgreSQL 0001→0014; restore | Şema drift yok; yedekten geri dönüş başarılı | ⏳ Bekliyor (SQLite QA + enum heal canlıda) |
| 8 | Fonksiyon | Test edilmemiş risk/olay/KKD/eğitim/CRM/finans/doküman/export | Her kritik CRUD ve hata akışı kanıtlı | ⚠️ Liste smoke var; derin CRUD kısmi |
| 9 | UI/PDF/Excel | Tarayıcı E2E, responsive, indirme ve görsel kalite | Rol menüsü/API uyumu ve dosya içeriği kabul edilir | ⏳ Bekliyor |
| 10 | Deploy | Render cold/ılık başlangıç, ağ hatası, izleme | Hedef süre/hata eşiği sağlanır | ✅ Public+auth smoke geçti (v0.9.59, CORS, oversight); uzun sleep cold hâlâ opsiyonel |

## Koşum özeti (izole)

| Suite | Sonuç |
| --- | --- |
| pytest | 17+ (rate-limit 429 birimi dahil) |
| `qa_api_smoke.py` | **45/45** |
| `qa_security_smoke.py` | **9/9** |
| `qa_retest_smoke.py` | **23/23** |
| `qa_live_render_smoke.py` | **15/15** (auth dahil; companies n=0 not) |

Kanıt: `docs/qa/logs/qa-retest-smoke.json`, `qa-api-smoke.json`, `qa-security-smoke.json`

## Çıkış kriteri

P0 bulgular kapalı, P1 bulgular için tekrar test geçmiş, canlıya özgü migration/deploy kanıtı mevcut ve sonuçlar bu rapor setine eklenmiş olmalıdır. Başarısız senaryo yeniden açılan bulgu olarak kaydedilir; başarı oranı tahmin edilmez.

**Kalan P1/P2:** İki-OSGB IDOR seed, upload AV, PostgreSQL/restore, UI E2E, Render cold-start.
