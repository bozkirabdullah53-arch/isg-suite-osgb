# İSG Suite v1.0 Üretim Kontrol Listesi

## Zorunlu güvenlik

- [ ] `SECRET_KEY` en az 32 rastgele karakter olmalı; örnek/değiştirilmesi gereken anahtar kullanılmamalıdır.
- [ ] `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` ve `DATABASE_URL` yalnızca ortam değişkenlerinden verilmelidir.
- [ ] Varsayılan global yönetici şifresi değiştirilmelidir.
- [ ] Production'da PostgreSQL ve HTTPS kullanılmalıdır; backend SQLite veya HTTP frontend origin'iyle başlamamalıdır.
- [ ] CORS yalnızca gerçek frontend alan adına açılmalıdır.
- [ ] SMTP, PostgreSQL, sağlık şifreleme ve yedek şifreleme sırları kaynak koduna yazılmamalıdır.
- [ ] Render'da `HEALTH_FIELD_ENCRYPTION_ENABLED=true` ve güçlü `HEALTH_FIELD_ENCRYPTION_KEY` tanımlı olmalıdır.
- [ ] Render'da `BACKUP_RESTORE_ENABLED=true`, `BACKUP_ENCRYPTION_KEY` tanımlı ve geri yükleme dry-run/staging testi tamamlanmış olmalıdır.
- [ ] Docker imajı `appuser` (UID 1000) ile çalışmalıdır.
- [ ] Dosyalar kalıcı nesne depolamada saklanmalı ve zararlı yazılım taraması etkin olmalıdır.
- [ ] Günlük otomatik yedekleme, geri yükleme ve geri dönüş prosedürü test edilmelidir.
- [ ] PyJWT ve frontend lockfile bağımlılıkları güncel/senkron olmalıdır.
- [ ] Access token `localStorage` içinde bulunmamalı; refresh cookie HttpOnly/Secure ve SameSite=Lax olmalıdır.
- [ ] Ayrıntılı sistem sağlık ve asenkron iş durumu endpoint'leri kimlik doğrulama gerektirmelidir; herkese açık `/health` yalnızca liveness için kullanılmalıdır.

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

## Yetkili Firma Yönetimi yayın kapısı

- [ ] `alembic current` çıktısı `0104_authorized_firm_compliance (head)` olmalıdır.
- [ ] OSGB yöneticisi yalnız kendi OSGB'sindeki firma kartlarını listeleyebilmeli; başka OSGB kartı kimliğiyle doğrudan istek kayıt varlığını açığa çıkarmadan `404` dönmelidir.
- [ ] Tek işyerine bağlı yönetici/kiosk hesapları `/api/v1/authorized-firms` uçlarına erişememelidir.
- [ ] Yetki, belge, profesyonel sertifikası, görevlendirme ve sözleşme tarih aralıkları ters girildiğinde kayıt reddedilmelidir.
- [ ] Aktif yetkili firma görevlendirmesi geçerli aktif sözleşme tarih aralığının dışına çıkamamalıdır.
- [ ] 30/60/90 günlük belge uyarıları ve bildirim yenileme akışı staging verisiyle doğrulanmalıdır.
- [ ] PDF, Excel, durum Excel'i ve denetim ZIP'i farklı tenant/rollerle indirme testinden geçmelidir.
- [ ] Excel formül enjeksiyonu ve PDF metin kaçışlama testleri geçmelidir.
- [ ] Firma kartı, Denetim Günü ve çıktılarda kişi/klinik sağlık ayrıntısı bulunmadığı doğrulanmalıdır.
- [ ] Uygunluk/kalite kategorileri, ağırlıklar, kritik engeller, önerilen aksiyonlar ve skor geçmişi kullanıcıya görünür olmalıdır.
- [ ] Production deploy yalnız backend testleri, frontend test/lint/build ve bağımlılık taramaları başarılı olduktan sonra yapılmalıdır.
- [ ] Migration öncesi PostgreSQL yedeği alınmalı; geri dönüşte yalnız yeni 0104 tablolarının kaldırılacağı doğrulanmalıdır.

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
