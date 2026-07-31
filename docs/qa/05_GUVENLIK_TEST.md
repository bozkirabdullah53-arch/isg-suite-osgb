# 05 — Güvenlik Test Değerlendirmesi

**Yöntem:** Kontrollü QA incelemesi; üretime saldırı testi yapılmadı. Bulgular, envanter/kod gözlemi ve sınırlı API smoke kanıtına dayanır.

| Alan | Kanıt / gözlem | Durum | Öncelik |
| --- | --- | --- | --- |
| JWT temel akışı | Login 200; hatalı parola 401; tokensız uç 401 | Kısmi geçti | P2 |
| JWT yaşam döngüsü | Refresh, iptal, süre aşımı ve token reuse senaryoları çalıştırılmadı | Test edilemedi | P2 |
| `SECRET_KEY` | Kodda varsayılan anahtar bulunduğu bildirildi | Prod ortamda güçlü sır zorunlu mu ölçülemedi | P0 koşullu |
| Rate limiting | `SimpleRateLimitMiddleware` mevcut, `main.py` içinde kayıt yok | Bilinen açık | P0 |
| Dosya yolu | Upload/dosya uçları mevcut | Path traversal ve yetki testi yapılmadı | P1 |
| Eğitim doğrulama | Public `/trainings/verify/{code}` geçersiz kodda 200/`valid:false` | Gerçek kodun PII döndürmesi test edilmedi | P1 |
| OpenAPI | `/openapi.json` QA’da 200 | Canlıda anonim açıklık ve veri sızıntısı değerlendirilmedi | P2 |

## Risk açıklamaları

- **Rate limit:** Login ve hassas uçlarda middleware kayıtlı değilse brute-force/deneme trafiği sınırlanmaz. Bu bulgu, `main.py` doğrulamasıyla kapatılmalıdır.
- **SECRET_KEY:** Varsayılan anahtarın üretimde kullanılması JWT imza güvenliğini etkiler. QA’da ayrı anahtar kullanıldı; canlı yapılandırma görülmediği için bu koşullu ama kritik bulgudur.
- **Dosyalar:** Kullanıcı girdili adlar, MIME/içerik kontrolü, indirme yetkisi ve dizin kaçışı ayrı test gerektirir.
- **Public verify:** İhtiyaç kadar veri döndürme ilkesi uygulanmalı; katılımcı adı, firma veya eğitim ayrıntısı gereksizse açığa çıkmamalıdır.
- **OpenAPI:** QA’da erişim beklenebilir; üretimde politika kararı verilmelidir. Açık bırakılırsa endpoint şemaları anonim kullanıcılara görünür.

## Sonuç

Bu turda penetrasyon testi yapılmadı. Rate limit kaydı ve üretim sır yönetimi doğrulanmadan güvenlik kabulü verilmemelidir. Düzeltme uygulanmadı.
