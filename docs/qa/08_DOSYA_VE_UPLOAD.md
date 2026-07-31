# 08 — Dosya ve Upload Değerlendirmesi

**Güncelleme:** 2026-07-20 — magic-byte + karantina (`0.9.61`)

| Konu | Gözlem | Durum |
| --- | --- | --- |
| Upload dizini | QA `./uploads_qa` | ✅ |
| Uzantı + MIME allowlist | pdf/xlsx/docx/png/jpg | ✅ |
| Magic-byte içerik doğrulama | EXE/ELF/`#!` reddi; uzantı-içerik uyumu | ✅ |
| Karantina | `uploads/_quarantine/` reddedilen içerik | ✅ |
| Path traversal | 404 | ✅ |
| Boyut sınırı | `max_upload_mb` | ✅ |
| İndirme yetkisi | Firma dışı 403 | ✅ smoke |
| Tam antivirüs motoru (ClamAV vb.) | Yok | ⚠️ Kabul riski / opsiyonel |

Kanıt: `qa_upload_export_smoke.json`, `tests/test_upload_security.py`
