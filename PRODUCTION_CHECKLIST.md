# İSG Suite v1.0 Üretim Kontrol Listesi

## Zorunlu güvenlik

- `SECRET_KEY` en az 32 rastgele karakter olmalı.
- Varsayılan global yönetici şifresi değiştirilmelidir.
- PostgreSQL kullanılmalıdır.
- HTTPS zorunlu olmalıdır.
- CORS yalnızca gerçek frontend alan adına açılmalıdır.
- SMTP parolası ve veritabanı parolası kaynak koduna yazılmamalıdır.
- Dosyalar kalıcı nesne depolamada saklanmalıdır.
- Zararlı yazılım taraması eklenmelidir.
- Günlük otomatik yedekleme ve geri yükleme testi yapılmalıdır.
- MFA ve parola sıfırlama sonraki güvenlik güncellemesinde tamamlanmalıdır.

## Yayın sırası

1. PostgreSQL veritabanını oluşturun.
2. Backend ortam değişkenlerini tanımlayın.
3. `alembic upgrade head` çalıştırın.
4. Backend `/health` ve `/api/v1/system/health` adreslerini kontrol edin.
5. Frontend `VITE_API_URL` değerini backend adresine yönlendirin.
6. Global yönetici ile giriş yapın.
7. Demo şifresini değiştirin.
8. Firma, şube ve kullanıcı erişim testlerini yapın.
9. Excel ve PDF dışa aktarımını test edin.
10. Dosya yükleme ve indirme erişimlerini farklı rollerle test edin.
11. Yedek alın ve test ortamına geri yükleyin.
12. Log ve uptime izleme hizmetini etkinleştirin.

## Ticari yayından önce kalan kritik entegrasyonlar

- Gerçek ödeme sağlayıcısı
- E-posta doğrulama ve parola sıfırlama
- MFA
- S3 / R2 dosya depolama
- ClamAV veya eşdeğer dosya taraması
- Redis tabanlı rate limiting
- Otomatik zamanlanmış bildirim görevleri
- KVKK aydınlatma, açık rıza ve veri saklama politikaları
- Penetrasyon testi
