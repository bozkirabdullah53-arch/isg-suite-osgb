# 06 — Performans Değerlendirmesi

**Durum:** Ölçüm bekleniyor. Bu turda yük testi, tarayıcı performans profili, Render cold-start ölçümü veya liste endpointi süre kaydı alınmadı.

| Ölçüm | Sonuç | Not |
| --- | --- | --- |
| Backend cold start | Ölçülemedi | Lokal import ve `/health` başarılı; süre loglanmadı |
| Render cold start | Ölçülemedi | Canlı ortam test edilmedi |
| Firma/personel liste süreleri | Ölçülemedi | Yanıt kodları doğrulandı, kronometre/percentile yok |
| Yıllık plan oluşturma | Ölçülemedi | 200 yanıt alındı; süre kaydı yok |
| PDF/Excel üretimi | Ölçülemedi | Endpoint içerik ve süre testi yapılmadı |
| Frontend build | 3,92 sn | Derleme süresidir; kullanıcı algılanan performans metriği değildir |

## Operasyonel gözlem

Canlıda bildirilen “Failed to fetch” davranışı, izole QA’da yıllık plan üretiminin 200 dönmesi nedeniyle iş kuralı hatası olarak doğrulanmadı. Render cold-start, ağ/proxy, CORS ve istemci zaman aşımı ayrıştırılmadan kök neden söylenemez.

## Önerilen kabul ölçümü

Canlıya geçişten önce üretime benzer PostgreSQL verisiyle soğuk/ılık başlangıç, kritik liste uçları, plan üretimi, PDF/Excel ve eşzamanlı login için p50/p95/p99, hata oranı ve kaynak kullanımını kaydedin. Kabul eşikleri iş gereksinimiyle onaylanmalıdır.
