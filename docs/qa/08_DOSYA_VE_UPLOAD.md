# 08 — Dosya ve Upload Değerlendirmesi

**Kapsam:** Envanter incelemesi. Binary upload/download HTTP testi yapılmadı.

| Konu | Gözlem | Durum |
| --- | --- | --- |
| Upload dizini | QA için ayrı `./uploads_qa` yapılandırıldı | Kısmi doğrulandı |
| Kullanım alanları | Sözleşme, ziyaret defteri, risk medya, sağlık raporu, KKD fotoğrafı | Mevcut |
| Antivirüs/malware tarama | Entegrasyon tespit edilmedi | Eksik / P1 |
| Path traversal | Test edilmedi | Test edilemedi / P1 |
| Dosya türü ve içerik doğrulama | Test edilmedi | Test edilemedi / P1 |
| Boyut sınırı ve kota | Test edilmedi | Test edilemedi / P2 |
| İndirme yetkisi | `/files` için kapsam uyumu belirsiz | Test edilemedi / P1 |
| UI binary yükleme | Doküman UI’da görünür binary yükleme akışı yok | UI/API uyumsuzluğu |

## Sonuç

Dosya depolama üretim için ayrıca ele alınmalıdır: uygulama dizininden ayrılmış, erişim kontrolü olan depolama; sunucu tarafından üretilen dosya adı; allowlist; boyut sınırı; içerik/malware taraması; güvenli indirme başlıkları ve audit kaydı önerilir. Bu turda path traversal güvenliğine ilişkin olumlu kanıt yoktur; “güvenli” kabul edilmemelidir.
