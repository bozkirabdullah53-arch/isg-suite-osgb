# 22 — O2/O3 Derin Arşiv Smoke Raporu

**Tarih:** 2026-07-20  
**Ortam:** İzole SQLite · canlı DB yok · **ürün kodu değiştirilmedi**  
**Script:** `backend/scripts/qa_eisa_archive_smoke.py`  
**Kanıt:** `docs/qa/logs/qa-eisa-archive-smoke.json`  
**Son koşum:** **54/54 PASS**

G1–G6 (önceki) + O2 (çapraz OSGB IDOR) + O3 (tüm silme→arşiv kancaları).

---

## Özet sayaç

| Durum | Sayı |
| --- | ---: |
| Başarılı | 54 |
| Başarısız | 0 |
| Atlanan | 0 |

---

## O2 — Çapraz-OSGB arşiv IDOR

| Test | Sonuç | Not |
| --- | --- | --- |
| OSGB1 tenant backup (GA) | PASS | |
| `test.osgb2.admin` OSGB1 arşiv indir | PASS **403** | `"Bu arşiv kaydına erişemezsiniz."` |
| OSGB2 liste OSGB1 kaydını göstermez | PASS | |

**Sonuç:** Çalışıyor — çapraz tenant arşiv indirme engelleniyor.

---

## O3 — Silme / değiştirme öncesi arşiv kancaları

| Kanca | Testler | Sonuç |
| --- | --- | --- |
| Doküman pasife | create → file upload → deactivate → `deleted_file` artışı | Çalışıyor |
| Ziyaret defteri değişimi | create → notebook×2 → arşiv artışı | Çalışıyor |
| Görev sözleşmesi değişimi | contract×2 → arşiv artışı | Çalışıyor |
| Sağlık raporu değişimi | create → report×2 → arşiv artışı | Çalışıyor |
| Risk medya (G5) | PNG upload → delete → arşiv | Çalışıyor |

---

## Gözlemler (ürün düzeltmesi yok — rapor)

| ID | Önem | Açıklama |
| --- | --- | --- |
| O-SEED-1 | Düşük / test | Seed’de uzman/hekim e-postası (`test.az.uzman@…`) ile profesyonel e-postası (`test.pro.safety_specialist@…`) eşleşmiyor; ziyaret oluşturma 400 veriyordu. Smoke fixture e-postayı hizalıyor (`o3_fixture_align_professional_email`). **Ürün bug’ı değil; seed veri tutarsızlığı.** |
| O2-CLOSED | — | Önceki rapordaki O2 (çapraz IDOR kanıtlanmamış) **kapatıldı** — 403 doğrulandı. |
| O3-CLOSED | — | Önceki O3 kapsam boşluğu **kapatıldı** — dört ek kanca + risk medya geçti. |

**P0 / kritik ürün hatası:** yok.

---

## G1–G6 (önceki tur, hâlâ yeşil)

Başvuru onay/red/sil, OSGB hard delete, abonelik Sil, `/archives`, EİSA rol 403 — hepsi PASS.

---

## Teslim

- Script + `qa_run_all` + runbook: önceki turda güncellendi  
- Bu rapor: `docs/qa/22_O2_O3_ARSIV_SMOKE_RAPORU.md`  
- Log: `docs/qa/logs/qa-eisa-archive-smoke.json`

## Önerilen sonraki adım (onayınla)

1. Seed’de profesyonel↔kullanıcı e-posta hizalaması (O-SEED-1) — isteğe bağlı kalite  
2. `qa_run_all` tam paketini O2/O3 dahil yeniden koşmak  
3. veya Aşama 8 / canlıya yeni özellik yoksa QA kapanış güncellemesi
