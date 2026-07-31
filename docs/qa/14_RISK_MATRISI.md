# 14 — Risk Matrisi

Ölçek: Olasılık ve etki 1 (düşük)–5 (çok yüksek). Skor = olasılık × etki; bu, test kanıtı eksik olan alanlarda ihtiyatlı önceliklendirmedir.

| Risk | Olasılık | Etki | Skor | Seviye | Gerekçe |
| --- | ---: | ---: | ---: | --- | --- |
| Rate-limit kaydı yok | 4 | 5 | 20 | Kritik | Kod envanterinde doğrudan bulgu |
| Prod `SECRET_KEY` varsayılanı | 3 | 5 | 15 | Yüksek | Canlı konfigürasyon görülmedi |
| Sağlık PII erişim boşluğu | 3 | 5 | 15 | Yüksek | Rol ayrımı kısmi, CA/alan/export eksik |
| Çok-tenant IDOR | 3 | 5 | 15 | Yüksek | Tek örnek geçiyor; tüm uçlar test edilmedi |
| Upload kötü amaçlı dosya/traversal | 3 | 4 | 12 | Yüksek | AV ve uç testleri yok |
| Eğitim verify PII | 3 | 4 | 12 | Yüksek | Public endpointin gerçek veri çıktısı ölçülmedi |
| Migration drift | 3 | 4 | 12 | Yüksek | Alembic dışı DDL riski |
| Render cold-start | 4 | 3 | 12 | Yüksek | Geçmiş kullanıcı etkisi, canlı test yok |
| PDF/Excel kalite/sızıntı | 3 | 3 | 9 | Orta | Görsel/içerik test edilmedi |
| PostgreSQL parity | 2 | 4 | 8 | Orta | SQLite ile sınırlı kanıt |

İlk aksiyonlar: P0’ları kapatın; ardından sağlık/tenant/upload sınırlarını gerçek HTTP senaryoları ile kanıtlayın.
