# 01 — Proje Envanteri (Aşama 1: Salt Okunur)

**Proje:** İSG Suite OSGB  
**Sürüm (kod):** `0.9.46` (`backend/app/main.py`)  
**Tarih:** 2026-07-20  
**Kapsam:** Kaynak kod analizi — kod değişikliği yok, canlı DB kullanılmadı.

---

## Özet envanter tablosu

| Alan | Tespit edilen yapı | Durum | Risk veya not |
| --- | --- | --- | --- |
| Frontend | React 19.2 + Vite 6.4, tek SPA (`main.jsx` shell), Lucide; `frontend/src/*.jsx` | Mevcut | TypeScript pakette var, kaynak JS; React Router yok |
| Backend | FastAPI, 23 router, `/api/v1` + kök `/health` | Mevcut | OpenAPI canlıda açık olabilir |
| Veritabanı | SQLAlchemy modelleri (~30 tablo); Alembic 0001–0012; SQLite local / PostgreSQL canlı | Mevcut | `create_all` + lifespan ALTER ile Alembic paralel → drift riski |
| Kimlik doğrulama | JWT (HS256), OAuth2 password, bcrypt/passlib | Mevcut | Varsayılan `SECRET_KEY` kodda; refresh/MFA yok |
| Yetkilendirme | `UserRole` 6 rol; `require_roles` + `company_access` (görevlendirme kapsamı) | Mevcut | Menü ≠ API yetkisi; izolasyon Aşama 4’te doğrulanacak |
| Dosya yönetimi | `UPLOAD_DIR`, multipart; sözleşme/ziyaret defteri/risk medya/sağlık raporu/PPE foto | Kısmi | Doküman UI’da binary yükleme yok; antivirüs yok |
| PDF | ReportLab + DejaVu font; eğitim, risk, olay, özet | Mevcut | Türkçe/taşma Aşama 3’te doğrulanacak |
| Excel | OpenPyXL; personel import, eğitim parse, risk/PPE/sağlık export | Mevcut | Büyük dosya / formül enjeksiyonu test edilmedi |
| Bildirim | `notifications` API + yeniden üretme servisi | Mevcut | SMTP isteğe bağlı; e-posta altyapısı UI’da “henüz yok” |
| Abonelik | `subscriptions` okuma + GA güncelleme | Kısmi | Ödeme sağlayıcısı **yok** |
| Yedekleme | `scripts/backup_database.py` (SQLite copy / pg_dump) | Mevcut | Yüklenen dosyalar ayrı; restore dokümante |
| Loglama | `AuditLog` + `services/audit.py`; güvenlik ekranından okuma | Kısmi | Tüm işlemlerin loglanıp loglanmadığı test edilmedi |
| Dış servisler | SMTP opsiyonel; ödeme/SMS/e-imza/İBYS/antivirüs/bulut depo **yok** | Eksik entegrasyon | Çalışıyor sayılmamalı |
| Rate limiting | `SimpleRateLimitMiddleware` yazılmış | **Kapalı** | `main.py`’de `add_middleware` yok → brute-force riski |
| Deploy | `render.yaml`, Docker Compose, frontend nginx SPA rewrite | Mevcut | Cold-start / Failed to fetch bilinen operasyonel risk |
| Otomatik test | 5 pytest dosyası (smoke, access unit, training, oversight) | Zayıf | HTTP/IDOR/sağlık gizlilik entegrasyon testi yok |

---

## 1. Klasör yapısı (özet)

```
isg-suite-osgb/
├── backend/app/{api,core,models,schemas,services}
├── backend/alembic/versions/0001…0012
├── backend/tests/
├── backend/scripts/ (seed, backup, audit smoke)
├── frontend/src/ (14 JSX + api.js)
├── render.yaml, docker-compose.yml
└── docs/
```

---

## 2. Roller ve menü matrisi (frontend)

| Rol | Menü anahtarları |
| --- | --- |
| `global_admin` | OSGB panel, denetim, performans, ÇSGB, profesyonel, görevlendirme, CRM, finans, işyerleri, şube, rapor, bildirim, abonelik, güvenlik, kullanıcı |
| `company_admin` | OSGB panel, profesyonel, görevlendirme, CRM, finans, İSG özeti, işyerleri, şube, personel, eğitim, doküman, rapor, bildirim, abonelik, güvenlik, kullanıcı |
| `safety_specialist` | Özet, ziyaret, risk, ramak/kaza/DÖF, KKD, eğitim, doküman, yıllık plan |
| `workplace_physician` / DSP | Özet, ziyaret, sağlık, personel, doküman, yıllık plan |
| `read_only` | Yalnız özet |

**Not:** Global yöneticinin eğitim/risk/sağlık menüsü yok (tasarım); API’de erişim ayrı test edilmeli.

---

## 3. Backend router özeti

| Prefix | Dosya | Ana işlev |
| --- | --- | --- |
| `/auth` | `auth.py` | login, me |
| `/companies`, `/branches`, `/users`, `/employees` | ilgili | firma/şube/kullanıcı/personel |
| `/health-records` | `health.py` | sağlık CRUD + analiz + export |
| `/annual-plans` | `annual_plans.py` | plan + otomatik üret |
| `/osgb` | `osgb.py` | OSGB, profesyonel, görevlendirme, denetim, ÇSGB |
| `/operations` | `operations.py` | dashboard, ziyaret, CRM, finans |
| `/trainings` | `trainings.py` | eğitim + PDF + public verify |
| `/risks`, `/incidents`, `/ppe` | ilgili | risk / olay / KKD |
| `/documents`, `/files`, `/exports` | ilgili | doküman meta / dosya / export |
| `/notifications`, `/subscriptions`, `/security`, `/dashboard`, `/reports`, `/system` | ilgili | destek modülleri |

---

## 4. Veri modeli (çekirdek ilişkiler)

- `osgb_organizations` → `isg_professionals`, `workplace_assignments`, `service_visits`, `crm_leads`, `finance_transactions`
- `companies` → employees, health, training, risk, incidents, documents, annual_plans
- `users` → birçok `created_by_id` FK (silmede yeniden atama gerekir — kısmen düzeltildi)
- `workplace_assignments`: `active` / `suspended` / `ended` + sözleşme dosyası

---

## 5. UI vs API boşlukları (koddan)

| Özellik | UI | API |
| --- | --- | --- |
| Firma/şube/personel düzenle-sil | Yok / zayıf | Kısmen var |
| Doküman binary dosya | Yok (yalnız meta + file_name metin) | `/files` var |
| CRM / finans düzenle-sil | Yok | Yok (yalnız GET/POST) |
| Abonelik ödeme | Yok | Yok |
| Görevlendirme sonlandır/askı/sil | Eklendi (0.9.46) | Eklendi |
| OSGB oluşturma | Yok | POST var |

---

## 6. Hipotez kritik riskler (henüz kanıtlanmadı — Aşama 4/5)

| # | Hipotez | Kaynak | Öncelik |
| --- | --- | --- | --- |
| H1 | Rate limit middleware kayıtlı değil | `main.py`, `rate_limit.py` | Yüksek |
| H2 | Varsayılan zayıf `SECRET_KEY` | `config.py` | Kritik (prod `.env` yoksa) |
| H3 | `COMPANY_ADMIN` sağlık klinik alanlarını görebilir; yalnız `confidential_note` hekim/GA | `health.py` | Kritik (gizlilik) |
| H4 | `/files` `user.company_id` ile kontrol; görevlendirme kapsamı ile uyumsuz olabilir | `files.py` | Yüksek |
| H5 | Eğitim `GET /trainings/verify/{code}` herkese açık, katılımcı adı sızdırabilir | `trainings.py` | Orta–Yüksek |
| H6 | Profesyonel–kullanıcı eşlemesi ada göre yanlış rol bağlayabilir | `company_access.py` | Yüksek |
| H7 | Alembic + lifespan ALTER drift | `main.py` | Orta |
| H8 | Render cold-start → Failed to fetch | Operasyon | Orta (bilinen) |

---

## 7. Mevcut otomatik testler

| Dosya | Kapsam |
| --- | --- |
| `test_smoke.py` | Parola hash |
| `test_company_access.py` | Kapsam unit |
| `test_training_topics.py` / `test_training_rules.py` | Eğitim kuralları |
| `test_osgb_oversight.py` | Denetim katalog |

**Eksik:** Auth HTTP, IDOR, sağlık gizlilik, upload güvenliği, migration CI.

---

## 8. Dış servis / entegrasyon durumu

| Servis | Durum |
| --- | --- |
| Ödeme | Yok |
| SMTP | Opsiyonel yapılandırma |
| SMS / e-imza / İBYS / e-reçete | Yok |
| Bulut dosya / antivirüs | Yok |
| İSG-KATİP API | Yok (manuel no + dosya) |

---

## 9. Aşama 1 sonucu

- Kaynak kod envanteri çıkarıldı.
- Canlı DB’ye yazılmadı, kod değiştirilmedi.
- Tam fonksiyon/güvenlik/izolasyon testleri **henüz çalıştırılmadı** → “çalışıyor” iddiası yok.

**Sonraki adım (Aşama 2):** İzole QA DB + ayrı `UPLOAD_DIR` ile backend/frontend smoke. Onayınızla başlanır. Canlıya deploy bu planda **yalnızca açık onayla**.

---

## Teslim kontrolü

| Zorunlu dosya | Bu aşamada |
| --- | --- |
| `01_PROJE_ENVANTERI.md` | ✅ Bu belge |
| `02_TEST_PLANI.md` | Taslak sonraki adım |
| Diğer 03–17 | Aşama 2–7 sonrası |
