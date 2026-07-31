# 09 — PDF ve Excel Değerlendirmesi

**Güncelleme:** 2026-07-20 — export içerik smoke

| Kontrol | Sonuç | Not |
| --- | --- | --- |
| `GET /exports/isg-summary.pdf` | ✅ | `%PDF` magic, >200 byte, `application/pdf` |
| `GET /exports/employees.xlsx` | ✅ | ZIP/`xl/` workbook, doğru MIME |
| UI menü E2E | ✅ | GA navigasyon (`10_UI_TARAYICI.md`) |
| Türkçe font görsel QA | ⚠️ | Piksel/görsel inceleme yok — kabul riski düşük |
| Excel formül enjeksiyonu | ⚠️ | Bu turda ayrı fuzz yok |

Kanıt: `docs/qa/logs/qa-upload-export-smoke.json`
