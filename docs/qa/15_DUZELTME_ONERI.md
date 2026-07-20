# 15 — Düzeltme Önerileri

**Uygulama durumu:** P0 maddeleri (Aşama 8) uygulandı; P1/P2 bekliyor.

| Öncelik | Öneri | Kabul kanıtı | Durum |
| --- | --- | --- | --- |
| P0 | `SimpleRateLimitMiddleware` kaydını uygulama başlangıcına ekleyin; login ve hassas uçlar için anahtar/pencere/429 politikasını belirleyin | Tekrarlı isteklerde 429, normal akışta regresyon yok | **Uygulandı** (`main.py`, 120 rpm) |
| P0 | Üretimde `SECRET_KEY` zorunlu, güçlü ve dışarıdan sağlanan sır yapın; varsayılanla prod başlatmayı engelleyin | Varsayılan sırla prod başlangıcı başarısız; token doğrulama geçti | **Uygulandı** (`validate_runtime_settings`) |
| P1 | Tüm kaynak router’larında merkezi tenant/assignment kontrolü uygulayın ve iki OSGB IDOR testleri ekleyin | Her rol ve nesne sınıfında izinli/izinsiz HTTP matrisi | Bekliyor |
| P1 | Sağlık alanlarını hekim/DSP ihtiyacına göre ayırın; CA, uzman, export ve audit kontrollerini test edin | Alan bazlı 403/maskleme ve audit kanıtı | Bekliyor |
| P1 | Upload için sunucu dosya adı, allowlist, boyut limiti, güvenli indirme ve AV/karantina ekleyin | Traversal, kötü MIME, büyük dosya ve yetkisiz indirme testleri | Bekliyor |
| P1 | Public eğitim verify yanıtını minimum veriye indirin veya imzalı/kısa ömürlü doğrulama kullanın | Gerçek/geçersiz kod PII sızıntı testi | **Kısmen** (geçersiz kodda participants/null alanlar gizlendi) |
| P2 | Alembic dışı şema mutasyonlarını kaldırın ya da migration’a taşıyın | Boş/mevcut PostgreSQL upgrade ve restore testi | Bekliyor |
| P2 | Cold-start ve ağ hatası için health/readiness, retry UX ve gözlemlenebilirlik ekleyin | Render tarayıcı akışında ölçülmüş p95 ve hata kaydı | Bekliyor |
| P2 | PDF/Excel/UI E2E test seti oluşturun | Görsel örnekler, export yetki testleri, CI raporu | Bekliyor |

Her değişiklik küçük, gözden geçirilebilir bir PR olarak; ilgili otomatik test ve tekrar test kanıtıyla birlikte sunulmalıdır.
