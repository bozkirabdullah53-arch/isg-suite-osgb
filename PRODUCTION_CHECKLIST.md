# İSG Suite v1.0 Üretim Kontrol Listesi

## Zorunlu güvenlik

- [ ] `SECRET_KEY` en az 32 rastgele karakter olmalı; örnek/değiştirilmesi gereken anahtar kullanılmamalıdır.
- [ ] `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` ve `DATABASE_URL` yalnızca ortam değişkenlerinden verilmelidir.
- [ ] Varsayılan global yönetici şifresi değiştirilmelidir.
- [ ] PostgreSQL ve HTTPS kullanılmalıdır.
- [ ] CORS yalnızca gerçek frontend alan adına açılmalıdır.
- [ ] SMTP, PostgreSQL, sağlık şifreleme ve yedek şifreleme sırları kaynak koduna yazılmamalıdır.
- [ ] Render'da `HEALTH_FIELD_ENCRYPTION_ENABLED=true` ve güçlü `HEALTH_FIELD_ENCRYPTION_KEY` tanımlı olmalıdır.
- [ ] Render'da `BACKUP_RESTORE_ENABLED=true`, `BACKUP_ENCRYPTION_KEY` tanımlı ve geri yükleme dry-run/staging testi tamamlanmış olmalıdır.
- [ ] Docker imajı `appuser` (UID 1000) ile çalışmalıdır.
- [ ] Dosyalar kalıcı nesne depolamada saklanmalı ve zararlı yazılım taraması etkin olmalıdır.
- [ ] Günlük otomatik yedekleme, geri yükleme ve geri dönüş prosedürü test edilmelidir.
- [ ] PyJWT ve frontend lockfile bağımlılıkları güncel/senkron olmalıdır.

## Yayın sırası

1. PostgreSQL veritabanını oluşturun ve tüm zorunlu sırları Dashboard'a tanımlayın.
2. `docker compose config` veya Render Blueprint doğrulamasıyla eksik ortam değişkenlerini kontrol edin.
3. `alembic upgrade head` çalıştırın.
4. Backend `/health` ve `/api/v1/system/health` adreslerini kontrol edin.
5. Frontend `VITE_API_URL` değerini backend adresine yönlendirin.
6. Global yönetici ile giriş yapın.
7. Demo şifresini değiştirin.
8. Firma, şube, tenant ve kullanıcı erişim testlerini yapın.
9. Excel ve PDF dışa aktarımını test edin.
10. Dosya yükleme ve indirme erişimlerini farklı rollerle test edin.
11. Sağlık alanı şifreleme readiness çıktısını ve yedek şifreleme anahtarını kontrol edin.
12. Yedek alıp önce dry-run, sonra staging geri yükleme testi yapın.
13. Log ve uptime izleme hizmetini etkinleştirin.

## Ticari yayından önce kalan kritik entegrasyonlar

- Gerçek ödeme sağlayıcısı
- E-posta doğrulama ve parola sıfırlama için gerçek SMTP teslimat testi
- S3 / R2 dosya depolama
- ClamAV veya eşdeğer dosya taraması
- Redis tabanlı rate limiting
- Otomatik zamanlanmış bildirim görevleri
- KVKK aydınlatma, açık rıza ve veri saklama politikaları
- Penetrasyon testi
