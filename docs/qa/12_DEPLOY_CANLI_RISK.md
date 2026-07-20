# 12 — Deploy ve Canlı Risk Değerlendirmesi

**Sınır:** Canlı Render servisi, canlı veritabanı ve production sırları bu turda test edilmedi.

| Risk | Kanıt | Etki | Durum |
| --- | --- | --- | --- |
| Render cold-start | Geçmiş “Failed to fetch” bildirimi; QA’da aynı iş kuralı 200 | Kullanıcı işlemi başarısız algılanabilir | Açık |
| Ağ/CORS/proxy | Tarayıcı-canlı akışı ölçülmedi | API erişimi kesilebilir | Doğrulanmadı |
| Canlı DB migration | PostgreSQL parity yok | Deploy sonrası şema hatası | Doğrulanmadı |
| Sır yapılandırması | Canlı `.env` incelenmedi | JWT güvenliği | Doğrulanmadı |
| Rate limit | Middleware kaydı yok bulgusu | Brute-force/abuse | Açık |
| Upload kalıcılığı | Dosya depolama ve yedek kapsamı doğrulanmadı | Veri kaybı/erişim | Doğrulanmadı |
| İzleme/rollback | Canlı runbook veya restore tatbikatı yok | Müdahale süresi uzar | Doğrulanmadı |

## Canlıya geçiş öncesi minimum kontrol

1. Render warm-up/cold-start davranışını gerçek tarayıcıdan, ağ kayıtlarıyla ölçün.
2. Üretim PostgreSQL migration ve geri dönüş prosedürünü yedek üzerinde doğrulayın.
3. Zorunlu güçlü `SECRET_KEY` ve kayıtlı rate-limit middleware doğrulamasını yapın.
4. Çok-tenant ve sağlık gizliliği tekrar testini tamamlayın.
5. Dosya depolama, yedek, izleme ve rollback sahiplerini/runbook’larını onaylayın.
