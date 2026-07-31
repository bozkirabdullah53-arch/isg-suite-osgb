# 20 — Delta / Regresyon (0.9.64 → 0.9.77)

**Tarih:** 2026-07-20  
**Ortam:** İzole SQLite `qa_isgsuite.db` · canlı DB kullanılmadı · deploy yok  
**Canlı health (gözlem):** `0.9.77` · `eisa_platform` · `central_archive` · `tenant_isolation`

## Önceki durum

Aşama 1–7 + kritik düzeltmeler `docs/qa/17_NIHAI_KARAR.md` ile **0.9.64**’te kapanmıştı.  
Bu tur: o karardan sonra gelen özelliklerin regresyonu + envanter güncellemesi.

## Kodda yeni (delta)

| Alan | Yapı | Durum |
| --- | --- | --- |
| EİSA SaaS paneli | `eisa` router + `eisa.jsx` (abonelik, ödeme, paket, OSGB kullanıcı, başvuru) | Mevcut — derin smoke **eksik** |
| Başvuru | `osgb_applications` + onay/red/sil | Mevcut — sil = yalnızca başvuru satırı |
| OSGB kalıcı sil | `DELETE /eisa/osgb-users/{id}` + `osgb_purge` + yedek | Mevcut — API smoke’da yok |
| Merkezi arşiv | `archives` API + `archive_store` + migration `0019` | Unit test OK; HTTP smoke **eksik** |
| Tenant izolasyon | `tenant_access` / strict tests | pytest OK |
| Migration | `0015`…`0019` | QA DB’de upgrade doğrulandı |

## Bu tur koşum

1. İlk `qa_run_all`: **4/7** — sebep: QA DB migration **0014’te kalmış** (0015–0019 yok) → CRUD create **500**.
2. `alembic upgrade head` + `seed_test_data.py` sonrası:
   - pytest **53** passed  
   - api **45/45**, security **9/9**, retest **29/29**, crud **20/20**, upload/export **10/10**, pdf **OK**  
   - **`qa_run_all` → 7/7**

Kanıt: `docs/qa/logs/qa-run-all.json`, `pytest-post-077.txt`, `alembic-qa-077.txt`.

## Kapsam boşlukları (otomatik smoke sonrası)

| # | Modül | Durum |
| ---: | --- | --- |
| G1 | EİSA başvuru onay/red/sil | ✅ `qa_eisa_archive_smoke` |
| G2 | OSGB kalıcı Sil + purge | ✅ |
| G3 | Abonelik Sil = aynı DELETE | ✅ |
| G4 | `/archives` backup/list/download | ✅ |
| G5 | Silme öncesi arşiv (risk + doküman + ziyaret + sözleşme + sağlık) | ✅ O3 derin smoke |
| G6 | GA SaaS / CA-uzman EİSA 403 | ✅ |

**Koşum (2026-07-20):** `qa_eisa_archive_smoke` → **54/54** · `docs/qa/22_O2_O3_ARSIV_SMOKE_RAPORU.md`  
O2 çapraz-OSGB arşiv IDOR: **403** doğrulandı.

## Gözlem

- Seed profesyonel e-posta ≠ saha kullanıcı e-postası → ziyaret create 400 (fixture ile aşıldı; ürün fix değil).

## Karar (bu tur)

- EİSA / arşiv / OSGB Sil / çapraz IDOR / silme kancaları: **çalışıyor (54/54)**.  
- P0 ürün hatası yok. Ürün kodu değiştirilmedi.
