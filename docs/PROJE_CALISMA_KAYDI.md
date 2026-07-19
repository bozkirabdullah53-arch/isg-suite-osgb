# İSG Suite OSGB — Çalışma Kaydı (Proje bitene kadar)

**Son güncelleme:** 2026-07-19 21:45 — Performans raporu + ÇSGB belge paketi  
**Aktif modül:** OSGB global profesyonel takip + ÇSGB denetim raporu

### OSGB Global yönetici yönü
- [x] Menüden kaldır: Eğitimler, Saha Takvimi (global_admin)
- [x] Seçilen uzman/hekim/DSP performans / iş tamamlama raporu
- [x] ÇSGB OSGB denetim belge paketi / rapor
- [ ] Commit/push + Render (`0.9.17`)

---

## 1) Kaynaklar ve yollar

| Ne | Yol / URL |
|----|-----------|
| OSGB Suite repo | `C:\Users\Abdullah\Projeler\isg-suite-osgb` |
| PRO 2026 (kaynak) | `C:\Users\Abdullah\OneDrive\Desktop\İSG PRO 2026` |
| PRO Eğitim | `...\İSG PRO 2026\Sistem\Moduller\egitim\` |
| Aktarım promptu (Eğitim) | `docs/EGITIM_PRO_AKTARIM_PROMPT.md` |
| Render notları | `RENDER_DEPLOY_FIX.md` |
| Git branch (çalışma) | `feature/training-ui-cors` |
| GitHub | `https://github.com/bozkirabdullah53-arch/isg-suite-osgb` |
| Canlı web | `https://www.isgsuite.tr` / Render web |
| Canlı API | `https://isg-suite-api-1u9t.onrender.com` |
| Render servisleri | `isg-suite-api-1u9t`, `isg-suite-web-1u9t` |

**Önemli (2026-07-19 11:15):** `origin/master` artık **force-push** ile `feature/training-ui-cors` ile aynı commit’te (`5846c2b`). GitHub tarafı güncel. Canlı OpenAPI hâlâ **eski** → Render otomatik almamış / cache / auto-deploy kapalı. **Clear build cache & Deploy şart.**

---

## 2) Kullanıcı kuralları (bu proje için)

1. Modülü **kullanıcı seçer** (şu an: Eğitim).
2. PRO kaynağı: verilen klasör (`İSG PRO 2026`).
3. Rapor: Türkçe madde listesi yeterli.
4. **Tek bölüm** — o bölüm full hatasız olmadan sonrakine geçilmez.
5. Türkçe yanıt tercih.
6. Commit/push kullanıcı canlıya alma isteğinde yapıldı; Render Clear cache deploy kullanıcı panelinden.

---

## 3) Tamamlanan aşamalar (kronolojik özet)

### A) Altyapı / genel
- [x] Suite: FastAPI + React, multi-tenant
- [x] Branch: `feature/training-ui-cors` Render blueprint’te hedef
- [x] Eğitim API: sessions, participants, Excel, logo, PDF, verify (kodda)
- [x] Risk modülü, Olay/Ramak, DÖF hub, KKD zimmet (kodda + push)
- [x] Risk medya + dashboard `open_risks` + Excel Fotoğraf (`5e4415b`)
- [x] KKD sol menü: **KKD Takip** (HardHat)

### B) Eğitim — kod tarafı (repo’da hazır)
- [x] PRO aktarım promptu: `docs/EGITIM_PRO_AKTARIM_PROMPT.md`
- [x] İmza formu layout: `KATILIMCI İMZA FORMU` / `İSG-EĞT-KF-01` (`training_pdfs.py`)
- [x] Katılım belgesi: mavi bant, konular 2 sütun, 6331 metin
- [x] Belge no formatı: `ISG-GGAAYYYY-001` (son commit)
- [x] Meta satırı: Süre │ Tür │ Şekil │ Doğrulama
- [x] Tür seçenekleri: İlk Defa / Tekrar (+ eski seçenekler)
- [x] `GET /trainings/layout-info` → `pdf_layout: pro-2026` (deploy doğrulama)
- [x] DejaVu font paketleme: `backend/app/assets/fonts/`
- [x] Doğrulama linki / sol menü düzeltmesi (`ff53710`):
  - Girişliyken `?egitim-dogrula=` shell’i bozmaz, query silinir, Eğitimler’e gider
  - Kamuya açık sayfa yalnız çıkışlı kullanıcıda
  - “Yeni sekmede aç” butonu

### C) Push’lanan son commit’ler (feature)
| Commit | Konu |
|--------|------|
| `96be405` | KKD zimmet |
| `15cf365` | Eğitim PDF PRO layout rebuild |
| `5e4415b` | Risk medya, open_risks, Excel foto |
| `a310aef` | Boş commit (redeploy tetik) |
| `1333ae6` | PRO prompt + belge no + layout-info |
| `ff53710` | Doğrulama URL / sidebar fix |
| `5846c2b` | Proje çalışma kaydı |
| *(aynı SHA master’a force-push)* | Canlı branch uyumu için |

---

## 4) AÇIK SORUNLAR (kritik — kullanıcı “hatalar devam ediyor”)

### P0 — Canlı API / Web eski sürümde (HÂLÂ — 11:15 ölçüm)
**Belirti (canlı OpenAPI):**
- Var: `attendance.pdf`, `sectors`, `expiring`, `overdue`
- Yok: `certificates.pdf`, `verify`, `layout-info`, `meta`, `parse-excel`
- İmza PDF hâlâ eski “EGITIM KATILIM…” (Helvetica / bozuk Türkçe)
- Katılım belgesi 404

**Yapılan:** GitHub `master` = `feature` = `5846c2b` (force-push).  
**Eksik:** Render panelinden deploy tetiklenmedi / cache temizlenmedi.

**Zorunlu (kullanıcı — ben Render’a giremiyorum):**
1. https://dashboard.render.com → giriş
2. `isg-suite-api-1u9t` → Branch `master` **veya** `feature/training-ui-cors` (ikiside aynı SHA)
3. **Manual Deploy → Clear build cache & deploy**
4. `isg-suite-web-1u9t` → aynı
5. Kontrol: `/api/v1/trainings/layout-info` → `pdf_layout: pro-2026`

### P1 — Eğitim (kodda kalan / deploy sonrası doğrulanacak)
- [ ] Canlı smoke: imza PDF + katılım belgesi + verify
- [ ] PDF görsel birebir PRO (`calisan_listesi (90).pdf` + imza formu görseli)
- [ ] Katılım/başarı beyanı PDF öncesi zorunlu mu?
- [ ] Kişi bazlı yoklama/puan UI
- [ ] Eğitim kaydı tam düzenleme
- [ ] Rapor Merkezi eğitim sayfaları (PRO parity)

### P2 — Sonraki modüller (Eğitim bitmeden başlama)
Kullanıcı sırayı söyler. Backlog örnek: Risk (edit UI, medya canlı), Ramak wizard, vs.

---

## 5) Referans dosyalar (PRO hedef çıktı)

- İmza formu: kullanıcı ekran görüntüsü — `İŞ SAĞLIĞI VE GÜVENLİĞİ TEMEL EĞİTİMİ KATILIMCI İMZA FORMU`
- Katılım belgeleri: `C:\Users\Abdullah\Downloads\calisan_listesi (90).pdf`

---

## 6) PC yeniden başladıktan sonra — kontrol listesi

1. Cursor’da workspace: `C:\Users\Abdullah\Projeler\isg-suite-osgb`
2. `git checkout feature/training-ui-cors` && `git pull`
3. Bu dosyayı oku: `docs/PROJE_CALISMA_KAYDI.md`
4. Render Clear cache deploy yapıldı mı? → `layout-info` kontrol
5. Eğitim smoke test (imza + belge + menü + doğrulama)
6. Eğitim OK ise kullanıcıya sor: sonraki modül?

---

## 7) Agent / sohbet notları

- Agent transcript (önceki): `C:\Users\Abdullah\.cursor\projects\c-Users-Abdullah-Projeler-isg-suite-osgb\agent-transcripts\b398ef05-df21-472f-8ae5-0cd2df65efe7\b398ef05-df21-472f-8ae5-0cd2df65efe7.jsonl`
- Canvases (eski analiz): `.cursor/projects/.../canvases/` (egitim-pro-gap, risk-ramak-kkd-plan, vb.)
- Yerel Python’da bazen `fastapi`/`reportlab` yok → import testleri ortam eksikliği; Render’da requirements ile kurulur.

---

## 8) Tek cümle durum

**Web canlıda YENİ, API canlıda ESKİ** → Eğitim PDF kırık. GitHub güncel (`master`=`feature`).  
**Çözüm:** API için Render **Clear build cache & Deploy** VEYA Deploy Hook’u GitHub secret’a ekle (`.github/workflows/render-deploy.yml`).  
Kontrol: `/health` → `version: 0.9.1` ve `pdf_layout: pro-2026` olmalı.
