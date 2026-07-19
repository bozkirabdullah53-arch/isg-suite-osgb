# İSG Suite OSGB — Çalışma Kaydı (Proje bitene kadar)

**Son güncelleme:** 2026-07-19  
**Amaç:** PC yeniden başlatma / oturum kesintisi sonrası kaldığımız yerden devam.  
**Kural:** Bir bölüm (modül) Suite’te **tam ve hatasız** çalışmadan sonraki moda geçilmez. Sırayı kullanıcı söyler.

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

**Önemli:** Default git branch `master` ile `feature/training-ui-cors` **ayrışmış** (unrelated/diverged). Yeni Eğitim PDF + KKD + risk medya kodu **feature** dalında. `master`’a merge push non-fast-forward reddedildi. Canlı muhtemel yanlış/eski branch veya cache’li deploy.

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

---

## 4) AÇIK SORUNLAR (kritik — kullanıcı “hatalar devam ediyor”)

### P0 — Canlı API / Web eski sürümde
**Belirti:**
- İmza PDF: eski `EGITIM KATILIM VE IMZA LISTESI` + bozuk Türkçe (siyah kutu)
- Katılım belgesi: `certificates.pdf yok` / 404
- Doğrulama API / layout-info canlıda yok veya 405
- OpenAPI’de yok: `certificates.pdf`, `verify/{code}`, `parse-excel`, `meta`, `layout-info`
- OpenAPI’de var (eski): `attendance.pdf`, `sectors`, `expiring`, `overdue`

**Kök neden:** Render deploy gelmiyor veya yanlış branch / build cache. Kod GitHub `feature/training-ui-cors`’ta güncel.

**Zorunlu işlem (kullanıcı / Render):**
1. `isg-suite-api-1u9t` → Settings → Branch = **`feature/training-ui-cors`**
2. Manual Deploy → **Clear build cache & deploy**
3. `isg-suite-web-1u9t` → aynı
4. Kontrol:  
   `https://isg-suite-api-1u9t.onrender.com/api/v1/trainings/layout-info`  
   → `{"pdf_layout":"pro-2026",...}` olmalı  
5. Sonra Eğitim: İmza PDF başlığı **KATILIMCI İMZA FORMU** olmalı; `certificates.pdf` inmeli

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

**Kod (feature) hazır; canlı Render eski API yüzünden Eğitim PDF + verify hâlâ bozuk. Bir sonraki adım: Clear cache deploy + layout-info doğrulama; sonra Eğitim smoke.**
