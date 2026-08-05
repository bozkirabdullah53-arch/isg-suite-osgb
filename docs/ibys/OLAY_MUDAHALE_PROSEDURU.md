# İBYS Entegrasyon ve Kişisel Veri Olay Müdahale Prosedürü

## 1. Amaç

İBYS entegrasyonu, OSGB tenant verileri, sağlık verileri, kimlik bilgileri veya entegrasyon credential’larıyla ilgili güvenlik olaylarının sınıflandırılması, sınırlandırılması, kanıtlanması ve kapatılması.

## 2. Olay sınıfları

- **Seviye 1 — Operasyonel:** Geçici timeout, başarısız test gönderimi, veri doğrulama reddi.
- **Seviye 2 — Güvenlik şüphesi:** Yetkisiz erişim denemesi, anormal trafik, mükerrer gönderim artışı, antivirüs uyarısı.
- **Seviye 3 — Veri güvenliği:** Tenant dışı erişim, hassas veri sızıntısı, credential ifşası, yedek bütünlüğü bozulması.
- **Seviye 4 — Kritik:** Geniş çaplı kişisel/sağlık verisi ihlali, production credential ele geçirilmesi, veritabanı bütünlüğü kaybı.

## 3. İlk müdahale

1. Olay kaydına benzersiz numara verilir.
2. Etkilenen ortam, tenant, kullanıcı, veri kategorisi ve zaman aralığı belirlenir.
3. Loglar değiştirilmeden korunur; secret ve kişisel veri rapora kopyalanmaz.
4. Gerekirse entegrasyon gönderimi feature flag ile durdurulur.
5. Etkilenen token/credential iptal edilir ve döndürülür.
6. Tenant izolasyonu şüphesinde ilgili servis erişimi kısıtlanır ve RLS davranışı doğrulanır.
7. Zararlı dosya şüphesinde dosya karantinaya alınır; indirme erişimi kapatılır.

## 4. Teknik kanıtlar

- Request ID ve kullanıcı/OSGB audit kayıtları
- Integration log id, adapter, kayıt sayısı ve durum
- Veritabanı Alembic head ve RLS policy envanteri
- Dosya/yedek SHA-256 checksum
- Deploy commit ve Render deploy id
- CI test sonucu ve ilgili regresyon testi

## 5. Bildirim ve karar

- Seviye 1 olaylar operasyon sorumlusu tarafından kapatılır.
- Seviye 2 olaylar güvenlik sorumlusuna yükseltilir.
- Seviye 3–4 olaylarda şirket yönetimi, hukuk/KVKK sorumlusu ve gerekiyorsa ilgili kamu otoritesi bilgilendirilir.
- Bildirim süresi ve kapsamı olay anındaki güncel mevzuat ve sözleşmeye göre hukuk/KVKK sorumlusu tarafından belirlenir.

## 6. Geri kazanım

1. Güvenli commit/config sürümü belirlenir.
2. Veritabanı migration’larında güvenliği kaldıran downgrade uygulanmaz; ileri yönlü düzeltme tercih edilir.
3. Restore gerekiyorsa checksum ve arşiv preflight zorunludur.
4. Hizmet yeniden açılmadan önce health, migration, tenant/RLS, kritik endpoint ve hata logları doğrulanır.
5. İBYS gönderimleri tekrar açılmadan önce test ortamında kontrollü gönderim yapılır.

## 7. Kapanış

- Kök neden
- Etki analizi
- Yapılan işlemler
- Veri sahibi/otorite bildirim kararı
- Kalıcı düzeltme
- Regresyon testi
- Sorumlu ve kapanış tarihi

alanları tamamlanmadan olay kapatılamaz.
