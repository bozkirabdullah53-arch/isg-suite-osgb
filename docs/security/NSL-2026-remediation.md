# NSL-2026 güvenlik düzeltmeleri

Bu kayıt kod değişiklikleri, doğrulama ve sağlayıcı işlemlerini ayırır. Kaynak rapor,
PDF şifresi, hesap bilgileri ve rapor ekran görüntüleri depoya eklenmemiştir.
Kod testlerinin geçmesi canlı sistemde tüm bulguların kapandığı anlamına gelmez.

| Bulgu | Uygulama durumu | Kalan doğrulama / işlem |
|---|---|---|
| NSL-202601 MFA atlatma | Önceki restart-setup 403 koruması korundu. Etkin MFA için kurulum tokenı reddedilir; enable tekrar çalıştırılamaz. Enable/disable token sürümünü artırır, access ve refresh birlikte yenilenir. Disable eski kurtarma kodlarını siler. Girişteki yeniden QR düğmesi kaldırıldı. | Yayından sonra yetkili test hesabıyla tekrar test. Rapor döneminde etkilenen hesaplar varsa kurtarma kodları ve oturumlar hesap sahibi doğrulanarak yenilenmeli. |
| NSL-202602 posta aktarımı | Mevcut zorunlu SMTP TLS koruması korundu. POP3 artık STLS olmadan kullanıcı adı/parola göndermez; POP3S/IMAPS ve STARTTLS varsayılan güvenilir sertifika doğrulaması kullanır. | Sağlayıcı TLS/HTTPS sunmalı veya posta hizmeti taşınmalı. Eski şifresiz sağlayıcıyla bağlantı güvenlik nedeniyle başarısız olur. |
| NSL-202603 parola püskürtme | Mevcut paylaşımlı dakikalık auth sınırına 10 dakikalık kaynak ve alt ağ sınırları eklendi; 429 ve Retry-After döner. Login hesap+IP kontrolü aynı proxy IP çözümünü kullanır. Redis hata verirse yerel koruma sürer. | Çoklu worker için REDIS_URL çalışmalı. TRUST_PROXY_HEADERS yalnız başlıkları güvenle yeniden yazan proxy arkasında açık tutulmalı. |
| NSL-202604 asistan HTML | Mevcut React metin gösterimi korunup ortak metin bileşeni ve gerçek DOM regresyon testiyle sabitlendi. Asistan mesajları HTML olarak yorumlanmaz. | Yayındaki frontend aynı sürüme gelmeli. JSON metin yanıtlarını kullanan diğer istemciler de HTML olarak yorumlamamalı. CSP'nin inline stillerini tüm uygulamada kaldırmak ayrı uyumluluk çalışmasıdır. |
| NSL-202605 hesap kilitleme | Önceki anonim hatalı girişlerin kalıcı hesap kilidi oluşturmaması korundu; başka kaynaktan doğru giriş test edildi. Kaynak ve alt ağ limiti ek koruma sağlar. | Yetkili test hesabıyla canlı retest. |
| NSL-202606 DMARC/DKIM | DNS bulgusu, kodla kapatılamaz. | Her iki alan adı için sağlayıcının DKIM anahtarı yayımlanmalı; SPF göndericilerle uyumlu olmalı. DMARC önce p=none, raporlar izlendiğinde quarantine/reject. Gerçek göndericiler doğrulanmadan reject uygulanmamalı. |
| NSL-202607 eski posta altyapısı | Üçüncü taraf sunucu/işletim sistemi, bu depoyla güncellenemez. | Sağlayıcı desteklenen platforma geçişi ve sürüm başlıklarının kaldırılmasını doğrulamalı veya posta hizmeti taşınmalı. |
| NSL-202608 Excel/CSV | Tüm uygulama XLSX kaydetme noktaları ortak güvenli dışa aktarım katmanına alındı. Metin hücreleri açıkça string türünde kaydedilir; tarih/sayı, stil, doğrulama ve koşullu biçimlendirme korunur. Üç CSV üreticisi ortak kaçış kullanır. Personel içe aktarımı formül hücrelerini açık hata ile reddeder. | Canlıdan alınan örnek dosyalarla retest. Veri raporları çalıştırılabilir hücre formülü üretmez. |
| NSL-202609 health bilgi ifşası | Önceki sabit liveness yanıtı korundu. Salt okunur canlı kontrol yanıtı yalnız status:ok içerdi. | Ayrıntılı bağımlılık teşhisi global_admin /system/infra-detail üzerinden yapılmalı; sabit liveness bağımlılıkların sağlıklı olduğunu kanıtlamaz. |

## Hız sınırları

Mevcut RATE_LIMIT_AUTH_RPM varsayılanı 30/dakika kalır. Login ve MFA verify için
LOGIN_SOURCE_WINDOW_LIMIT=60 ve LOGIN_SUBNET_WINDOW_LIMIT=200 ek 600 saniyelik
pencerelerde uygulanır. IPv4 /24, IPv6 /64 kullanılır. Ortak hastane/OSGB NAT
kapasitesine göre ayarlanabilir. Bellek yedeği worker başına çalışır; merkezi
koruma Redis gerektirir. Başlık güven zinciri dağıtımda doğrulanmalıdır.

## Ek bağımlılık düzeltmesi

GitHub bağımlılık denetimi mevcut üretim PyJWT 2.13.0 için güvenlik bulguları
bildirdi. Hem backend hem kök manifestte PyJWT 2.14.0 sabitlendi. Üretim
manifestiyle `pip-audit --strict` yeniden çalıştırıldı: bilinen açık bulunmadı.
Sürüm kaynağı: https://github.com/jpadilla/pyjwt/releases/tag/2.14.0

## Doğrulama

- Etkilenen backend güvenlik, giriş, e-posta, personel, rapor ve asistan testleri:
  üretim bağımlılıkları ve PyJWT 2.14.0 ile son koşuda 195 geçti; bir ilgisiz mevcut test ayrı tutuldu.
- Bireysel kayıt testinin eski `osgb_id is None` beklentisi mevcut bireysel özel
  çalışma alanı davranışıyla uyuşmuyor; ilk test koşusunda da başarısızdı.
  Bu değişiklikte üyelik davranışı veya o testin beklentisi değiştirilmedi.
- MFA/refresh ek test koşusu: 27 geçti; son MFA oturum testleri ayrıca çalıştırıldı (20 geçti).
- Frontend asistan/giriş: 18 test geçti; HTML/CSS/form/meta etiketleri DOM oluşturmadı.
- `npm run build` geçti. Staging Playwright kart kontrolü script tarafından staging
  dışında atlandı; canlı uçtan uca kontrol yapıldığı iddia edilmez.
- `git diff --check` ve Python derleme kontrolü geçti.

## Yayın ve kapanış

Kod düzeltmeleri ayrı branch/PR'dadır. Posta/DNS bulguları sağlayıcı tarafından
kapatılmadan raporun tümünün kapandığı söylenemez. Yayın öncesinde posta TLS
geçişi planlanmalı: bağlantı sorunu düz metin kimlik doğrulamaya dönerek giderilmemeli.
Canlı retest gerçek kullanıcı hesaplarını kilitlemeden, yetkili test hesabıyla yapılmalı.
