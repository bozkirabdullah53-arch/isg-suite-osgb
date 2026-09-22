# İBYS Başvuru Sunumu — Akış ve Kanıt Listesi

**Hedef süre:** 15–20 dakika sunum + canlı demo  
**Hedef slayt:** 12–15

## Slayt akışı

1. **Kapak**
   - İSG Suite
   - www.isgsuite.tr
   - İBYS Entegratör Başvurusu
   - Firma/yetkili bilgisi

2. **Ürün ve amaç**
   - Web tabanlı İSG yönetim platformu
   - OSGB, işyeri, uzman, hekim ve çalışan rolleri
   - Çoklu firma/tenant yapısı

3. **Teknik mimari**
   - Frontend
   - FastAPI backend
   - PostgreSQL
   - Object storage
   - Secret management
   - HTTPS/TLS

4. **Kimlik, rol ve tenant izolasyonu**
   - RBAC
   - Firma/OSGB kapsamı
   - Yetkisiz çapraz firma erişiminin engellenmesi

5. **İSG veri alanları**
   - Eğitim
   - Sağlık gözetimi
   - Risk/tehlike kaynakları
   - Olay/ramak kala
   - Doküman ve diğer destek modülleri

6. **İBYS veri hazırlığı**
   - Alan eşleme
   - Validasyon
   - TCKN/kimlik doğrulama yaklaşımı
   - Resmî Bakanlık şeması gelene kadar fail-closed adapter

7. **E-imza altyapısı**
   - İmza isteği
   - SHA-256
   - nonce/tek kullanım
   - PKCS#11
   - Resmî profil/test erişimi sonrası aktive edilecek bağlantı

8. **Veri yedekleme**
   - Günlük otomatik yedek
   - Şifreleme
   - Uzak kopya
   - Checksum
   - Retention
   - Alarm

9. **Geri yükleme ve felaket kurtarma**
   - Dry-run
   - Staging
   - Yetkili onay
   - Restore doğrulama
   - RPO/RTO

10. **Veritabanı değişiklik / veri düzeltme süreci**
    - Talep numarası
    - Maker-checker
    - Önce/sonra değer
    - Gerekçe
    - Transaction
    - Rollback

11. **Değişmez audit izi**
    - Append-only
    - prev_hash/event_hash
    - audit_chain_verify
    - Tahrifat tespiti

12. **Hassas veri ve KVKK güvenliği**
    - Sağlık alanı şifreleme
    - Yetki
    - Veri minimizasyonu
    - Log redaksiyonu
    - Secret yönetimi

13. **Operasyon ve izleme**
    - Migration
    - CI/test
    - Hata kayıtları
    - Yedek alarmı
    - Güvenlik kontrolleri

14. **Canlı demo**
    - Anonim firma
    - Personel
    - Eğitim/sağlık/risk kaydı
    - Veri düzeltme talebi
    - Audit log
    - Yedek ve bütünlük kontrolü

15. **Başvuru/test aşaması**
    - Güncel başvuru evrakları
    - İSGGM randevu
    - Bakanlığın resmî teknik profil/test erişimi
    - Contract test
    - Kontrollü devreye alma

## Sunumda kullanılacak teknik kanıtlar

- Uygulama giriş ve rol ekranları.
- Tenant/firma seçimi ve izolasyon örneği.
- Eğitim veri ekranı ve belge doğrulama örneği.
- Sağlık kayıt erişim yetkisi örneği.
- Risk değerlendirme/revizyon örneği.
- Global audit log ekranı.
- `GET /api/v1/security/audit-chain` sonucu.
- Son başarılı yedek listesi.
- Checksum doğrulaması.
- Restore tatbikat raporu.
- Veri düzeltme talebi ve onay ekranı.
- Alembic migration/CI sonucu.
- HTTPS/TLS ve güvenlik başlıkları.
- Secret değerlerini göstermeden sadece konfigürasyon varlığı.

## Sunum dili için kurallar

- "Bakanlık onaylı", "entegrasyon tamamlandı", "canlı veri gönderiyoruz" ifadeleri resmî onay/test tamamlanmadan kullanılmaz.
- "Kod tarafı hazır", "başvuru/test aşamasında resmî profil ile bağlanacak", "fail-closed" ifadeleri gerçek durumu doğru anlatır.
- Ekran görüntülerinde gerçek TCKN, sağlık verisi, e-posta, telefon veya başka kişisel veri bulunmaz.
- Tüm demo kayıtları sentetik/anonim olmalıdır.
