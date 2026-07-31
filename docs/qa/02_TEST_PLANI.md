# 02 — Test Planı (Taslak)

**Durum:** Aşama 1–7 belgelendi; Aşama 8 için kullanıcı onayı bekleniyor.  
**Kural:** Canlı DB kullanılmaz. Test kayıtları `TEST_` / `QA_` önekli. Düzeltme yalnızca hata listesi onayından sonra.

---

## Ortam gereksinimleri (Aşama 2)

| Öğe | Değer |
| --- | --- |
| DB | Ayrı PostgreSQL veya `sqlite:///./qa_isgsuite.db` |
| Upload | `./uploads_qa` |
| Backup | `./backups_qa` |
| Seed | `SEED_ADMIN_*` yalnızca QA |
| API | `localhost:8000` |
| Web | `localhost:5173` + `VITE_API_URL` |

---

## Çalışma sırası (özet)

| Aşama | İçerik | Durum |
| --- | --- | --- |
| 1 | Salt okunur envanter | ✅ |
| 2 | Çalıştırma + smoke + mevcut pytest | ✅ (`02B_SMOKE_SONUCLARI.md`) |
| 3 | Modül fonksiyon testleri | ✅ Belgelendi; kapsam kısmi (`03_FONKSIYON_TEST_RAPORU.md`) |
| 4 | Yetki + OSGB/firma izolasyonu + sağlık gizlilik | ✅ Belgelendi; tam kanıt yok (`04_YETKI_VE_IZOLASYON.md`) |
| 5 | Güvenlik (kontrollü) | ✅ Belgelendi; P0/P1 açık (`05_GUVENLIK_TEST.md`) |
| 6 | Performans (ölçekli veri) | ✅ Belgelendi; ölçüm bekleniyor (`06_PERFORMANS.md`) |
| 7 | Raporlar 03–17 | ✅ Tamamlandı; hiçbir bulgu için düzeltme uygulanmadı |
| 8 | Düzeltme | ⏳ Yalnızca kullanıcı onayı sonrası |

---

## Smoke checklist (Aşama 2 — önerilen)

1. `python -m venv` + `pip install -r requirements.txt`
2. `alembic upgrade head` temiz DB
3. `uvicorn` → `/health`, `/docs`
4. `pytest -v`
5. `npm ci` + `npm run build`
6. Login → her rol için menü açılışı (görüntüleme ≠ fonksiyon onayı)
7. Docker Compose (opsiyonel)

---

## Öncelikli hipotez doğrulama sırası (Aşama 4–5)

1. Firma/OSGB IDOR  
2. Sağlık verisi → `company_admin` / uzman  
3. JWT secret / rate limit  
4. `/files` kapsamı  
5. Public training verify PII  

---

## Karar çerçevesi (Aşama 7 sonunda)

Tek karar: **CANLIYA ALINABİLİR** | **KRİTİK DÜZELTMELERDEN SONRA** | **CANLIYA ALINMAMALI**
