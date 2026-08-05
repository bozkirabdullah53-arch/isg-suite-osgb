# İBYS Başvuru Hazırlığı Teknik Kanıt Raporu

## 1. Kapsam

Bu rapor, İSG Suite OSGB yazılımının İBYS entegratör **başvuru hazırlığı** için oluşturulan aday veri profili, doğrulama altyapısı ve başvuru dosyasının teknik kanıtlarını kaydeder. Bakanlık tescili veya resmî İBYS şemasına uygunluk beyanı değildir.

## 2. Git ve inceleme kaydı

- Ana geliştirme branch’i: `agent/ibys-application-readiness`
- Master hedefli taslak PR: `#51`
- Staging aktarım PR: `#53`
- Staging merge commit: `c8dc8fe90f0f4c98bd6e27fa208a63690dc39871`
- Değişen dosya sayısı: 15
- Production/master durumu: Değişmedi; PR #51 taslak bırakıldı.

## 3. CI kanıtı

- GitHub Actions run: `#412`
- Run id: `30973651076`
- Sonuç: Başarılı

Başarılı iş grupları:

- Backend SQLite smoke
- Backend PostgreSQL
- Alembic upgrade head
- PostgreSQL schema parity
- İBYS aday profil regresyon testleri
- Frontend test
- Frontend lint
- Frontend build
- E2E smoke
- Dependency audit

## 4. Staging kanıtı

- Render service: `isg-suite-api-staging`
- Service id: `srv-d9o9vn142hec73916b10`
- Deploy id: `dep-d9pbb2r7uimc739g0ucg`
- Deploy commit: `c8dc8fe90f0f4c98bd6e27fa208a63690dc39871`
- Deploy sonucu: `live`
- Migration sonucu: `=== Migrations OK ===`
- Uygulama sonucu: `Application startup complete`
- Port: `0.0.0.0:10000`

Staging servisi ücretsiz plan üzerinde ve Render `healthCheckPath` ayarı boş durumdadır. Uygulamanın gerçek sağlık uç noktası `/health` olmakla birlikte platform ayarının ayrıca `/health` olarak düzeltilmesi operasyonel iyileştirme kalemidir.

## 5. Aday İBYS profil kanıtı

- Profil sürümü: `application-candidate-v1`
- Aday veri seti: 12
- Resmî uygunluk iddiası: `false`
- Resmî sözleşme durumu: `awaiting_ministry_contract`
- Zorunlu alan doğrulaması: Mevcut
- Kayıt fingerprint’i: SHA-256
- İdempotency anahtarı: Veri seti + OSGB + profil + kayıt fingerprint’leri
- Kayıt bazlı kabul/ret: Mevcut
- Hassas veri ret raporuna yazılmaz: Regresyon testi mevcut
- Harici İBYS HTTP çağrısı: Yok

## 6. Yetkilendirme kanıtı

Yeni API’ler `GLOBAL_ADMIN` ve `COMPANY_ADMIN` rolleriyle sınırlıdır. Şirket yöneticisi farklı OSGB id’siyle aday zarf oluşturamaz. Router kayıtları ve rol/scope kodu CI testinde doğrulanmıştır.

Dış doğrulama çalışma ortamında DNS çözümleme kısıtı bulunduğundan staging URL’sine araç dışından yetkisiz HTTP isteği üretilememiştir. Bu kontrol yapılmış gibi gösterilmemiş; production öncesi gerçek tarayıcı/API smoke listesinde açık tutulmuştur.

## 7. Açık başvuru kapıları

1. Başvuru sahibi şirketin kurumsal evrakları
2. Ticari unvan, vergi numarası, MERSİS, adres ve yetkili bilgilerinin dilekçeye işlenmesi
3. İmza sirküleriyle başvuru yetkisinin doğrulanması
4. Hukuk/KVKK sorumlusunun hukuki sebep ve saklama sürelerini onaylaması
5. İSGGM’den güncel başvuru evrak listesinin yazılı teyidi
6. Randevu talebinin yetkili kişi tarafından gönderilmesi
7. Staging servisinin `healthCheckPath=/health` olarak yapılandırılması

## 8. Sonuç

Teknik aday profil, doğrulama motoru, CI ve staging deploy’u tamamlanmıştır. Başvuru hazırlığının kalan bölümü ağırlıklı olarak başvuru sahibi şirketten alınacak resmî belgeler, hukuki onay ve yetkili imzadır. Resmî İBYS veri sözleşmesi ve Bakanlık kabul testleri, başvurudan sonraki ayrı teknik aşamadır.
