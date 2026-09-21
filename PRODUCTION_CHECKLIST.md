# İSG Suite v1.0 Üretim Kontrol Listesi

## Zorunlu güvenlik

- [ ] `SECRET_KEY` en az 32 rastgele karakter olmalı; örnek/değiştirilmesi gereken anahtar kullanılmamalıdır.
- [ ] `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` ve `DATABASE_URL` yalnızca ortam değişkenlerinden verilmelidir.
- [ ] Varsayılan global yönetici şifresi değiştirilmelidir.
- [ ] Production'da PostgreSQL ve HTTPS kullanılmalıdır; backend SQLite veya HTTP frontend origin'iyle başlamamalıdır.
- [ ] CORS yalnızca gerçek frontend alan adına açılmalıdır; production'da localhost olmamalıdır.
- [ ] HSTS `includeSubDomains; preload` açık olmalıdır.
- [ ] `/.well-known/security.txt` ve `/robots.txt` yayınlanmalıdır.
- [ ] SMTP, PostgreSQL, sağlık şifreleme ve yedek şifreleme sırları kaynak koduna yazılmamalıdır.
- [ ] Render'da `HEALTH_FIELD_ENCRYPTION_ENABLED=true` ve güçlü `HEALTH_FIELD_ENCRYPTION_KEY` tanımlı olmalıdır.
- [ ] Render'da `BACKUP_RESTORE_ENABLED` varsayılan **false** olmalıdır (F-04); gerçek geri yükleme yalnızca bakım penceresinde, dry-run + staging testi tamamlandıktan sonra geçici açılır.
- [ ] **F-01 (bloke):** mevcut posta sağlayıcısı hiçbir şifreli portu desteklemiyor (587 STARTTLS yok, 465/993/995 kapalı, POP3 STLS yok — 2026-09-21 probe). Sağlayıcıda TLS etkinleştirilene veya SMTP relay + IMAPS posta kutusuna geçilene kadar e-posta trafiği düz metindir; parola sıfırlama token TTL'ini kısa tutun ve geçişi planlayın.
- [ ] Access/MFA token üçüncü taraf QR servisine (qrserver vb.) gönderilmemeli; QR yalnızca backend üretimi data URL ile gösterilmelidir (F-08).
- [ ] Docker imajı `appuser` (UID 1000) ile çalışmalıdır.
- [ ] Dosyalar kalıcı nesne depolamada saklanmalı ve zararlı yazılım taraması etkin olmalıdır.
- [ ] Günlük otomatik yedekleme, geri yükleme ve geri dönüş prosedürü test edilmelidir.
- [ ] PyJWT ve frontend lockfile bağımlılıkları güncel/senkron olmalıdır.
- [ ] Access token `localStorage` içinde bulunmamalı; refresh cookie HttpOnly/Secure ve SameSite=Lax olmalıdır.
- [ ] Ayrıntılı sistem sağlık ve asenkron iş durumu endpoint'leri kimlik doğrulama gerektirmelidir; herkese açık `/health` yalnızca liveness için kullanılmalıdır.
- [ ] Migration `0122`–`0125` açılışta `alembic upgrade head` ile uygulanır; deploy sonrası global admin ile `GET /api/v1/security/audit-chain` → `supported=true, ok=true, chain_breaks=0, hash_breaks=0` doğrulanmalıdır.
- [ ] Kullanıcı/OSGB kalıcı silme akışları 0122 sonrası detach-safe'tir; atıf olayları (`audit_actor_detach`, `audit_company_detach`) audit trail'de görünmelidir (regresyon: `test_audit_chain.py`, `test_osgb_purge.py`).
- [ ] İSG-KATİP 48 saatlik yetkilendirme penceresi runbook'u: `docs/IBYS_PRODUCTION_READINESS_2026-09-21.md` §1 — pencere açılmadan `integration-readiness` + `katip-prep/export.csv` + `sync-field-roles` tamamlanmış olmalıdır.

## Yayın sırası

1. PostgreSQL veritabanını oluşturun ve tüm zorunlu sırları Dashboard'a tanımlayın.
2. `docker compose config` veya Render Blueprint doğrulamasıyla eksik ortam değişkenlerini kontrol edin.
3. `alembic upgrade head` çalıştırın.
4. Backend herkese açık `/health` liveness yanıtını ve global yönetici kimliğiyle `/api/v1/system/health` yanıtını kontrol edin.
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
- Resmi İBYS/İSG-KATİP API sözleşmesi, erişim bilgileri ve sandbox/contract testleri
- KVKK aydınlatma, açık rıza ve veri saklama politikaları
- Penetrasyon testi
