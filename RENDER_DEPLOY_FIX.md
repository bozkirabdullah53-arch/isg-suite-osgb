# Render deploy düzeltmesi

Bu sürüm Render build hatası için hazırlanmıştır.

## Zorunlu işlem (Eğitim PDF hâlâ eskiyse)

Render servislerinde branch **mutlaka** `feature/training-ui-cors` olsun.
`master` dalında PRO imza/belge PDF kodu yok / eski.

1. **isg-suite-api-1u9t** → Settings → Branch = `feature/training-ui-cors`
2. Manual Deploy → **Clear build cache & deploy**
3. **isg-suite-web-1u9t** → aynı
4. Deploy sonrası kontrol:
   - `https://isg-suite-api-1u9t.onrender.com/api/v1/trainings/layout-info`
     → `pdf_layout: "pro-2026"` dönmeli
   - OpenAPI’de `certificates.pdf` + `verify/{code}` görünmeli
   - İmza PDF dosya adı: `...-katilimci-imza-formu-PRO.pdf`
   - Başlık: **KATILIMCI İMZA FORMU** (EGITIM KATILIM… değil)

Aktarım promptu: `docs/EGITIM_PRO_AKTARIM_PROMPT.md`

## Frontend beklenen ayarlar

- Root Directory: `frontend`
- Build Command: `npm ci --no-audit --no-fund && npm run build`
- Publish Directory: `dist`
- Node: `20.18.0` (engines: `>=20 <21`)
- Branch (canlı eğitim sürümü): `feature/training-ui-cors`

Repo kökünde ve frontend klasöründe `.node-version` / `.nvmrc` dosyaları bulunmaktadır.
