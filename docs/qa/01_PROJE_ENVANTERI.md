# 01 — Proje Envanteri (Aşama 1: Salt Okunur)

**Proje:** İSG Suite OSGB  
**Sürüm (kod / canlı):** `0.9.77` (`backend/app/main.py`)  
**Tarih:** 2026-07-20 (güncelleme: EİSA + arşiv delta)  
**Kapsam:** Kaynak kod analizi — bu dosyanın ilk sürümü 0.9.46 içindi; aşağıdaki tablo 0.9.77’ye güncellendi.

> Delta regresyon: [`20_DELTA_REGRESSION_077.md`](20_DELTA_REGRESSION_077.md)

---

## Özet envanter tablosu

| Alan | Tespit edilen yapı | Durum | Risk veya not |
| --- | --- | --- | --- |
| Frontend | React 19 + Vite 6 SPA; `main.jsx` + `eisa.jsx` + modül JSX | Mevcut | React Router yok; GA menüsü SaaS-only |
| Backend | FastAPI, ~26 router (`eisa`, `osgb_applications`, `archives` dahil), `/api/v1` + `/health` | Mevcut | OpenAPI prod’da açık olabilir |
| Veritabanı | SQLAlchemy; Alembic **0001–0019**; SQLite local / PostgreSQL canlı | Mevcut | QA DB migration drift → smoke 500 (bu turda düzeltildi) |
| Kimlik doğrulama | JWT HS256, OAuth2 password, bcrypt | Mevcut | MFA / refresh yok |
| Yetkilendirme | 6 rol + `company_access` + `tenant_access` | Mevcut | GA tüm tenant; izolasyon pytest + smoke OK |
| Dosya yönetimi | Multipart; magic-byte + karantina; ClamAV opsiyonel | Kısmi | ClamAV prod’da disabled (risk kabulü) |
| PDF / Excel | ReportLab DejaVu / OpenPyXL | Mevcut | Smoke OK |
| Bildirim | OSGB deadline scan + EİSA platform bildirimleri | Mevcut | SMTP opsiyonel |
| Abonelik | OSGB subscription + EİSA paket/ödeme (manuel) | Kısmi | Ödeme gateway **yok** |
| Yedekleme | `backup_database.py` + **merkezi arşiv** (`central_archive`) | Mevcut | Tenant zip + silme öncesi kopya; HTTP smoke eksik |
| Loglama | `AuditLog` + EİSA old/new | Mevcut | — |
| Dış servisler | SMTP opsiyonel; ödeme/SMS/e-imza/İBYS/AV motoru yok | Eksik entegrasyon | Çalışıyor sayılmamalı |
| Rate limiting | `SimpleRateLimitMiddleware` (120 rpm) | Mevcut | Kayıtlı |
| Deploy | Render + Docker Compose | Mevcut | Warm-up cron |
| Otomatik test | pytest 53 + 6 smoke script | Mevcut | EİSA/arsiv HTTP smoke henüz yok |

---

## 1. Klasör yapısı (özet)

```
isg-suite-osgb/
├── backend/app/{api,core,models,schemas,services}
├── backend/alembic/versions/0001…0019
├── backend/tests/
├── backend/scripts/ (seed, backup, qa_*.py)
├── frontend/src/ (main/eisa + modül JSX)
├── render.yaml, docker-compose.yml
└── docs/qa/
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
