# NSL-202602 — Gelen posta TLS düzeltmesi ve yayın koşulları

2 Ekim 2026. Kullanıcı güvenlik düzeltmelerini yetkilendirdi ve çalışma deposunu
`bozkirabdullah53-arch/isg-suite-osgb` olarak belirtti. Bu değişiklik yayın onayı
istemek için değil, mevcut sağlayıcıyla çalışacağı kanıtlanmadan posta akışını
bozmamak için provider-pending PR #473 kapsamında tutulur.

## Uygulanan kod düzeltmesi

- IMAP implicit TLS ve STARTTLS, doğrulanan sistem CA deposunu ve alan adı
  kontrolünü kullanır.
- POP3 implicit TLS aynı sertifika doğrulamasını kullanır.
- POP3 açık bağlantıda kullanıcı/parola gönderilmeden önce doğrulanan STLS
  zorunludur. TLS desteklenmiyorsa düz metne geri dönüş yapılmaz.
- Mevcut uç noktalar, kullanıcı bilgileri, portlar, kuyruklar ve kayıtlar
  değiştirilmedi. SMTP'nin mevcut zorunlu TLS koruması korundu.
- Yerel gerçek IMAP/POP3 sunucularıyla untrusted/expired/wrong-host sertifikalar,
  reddedilen STLS ve geçerli şifreli giriş sınandı. Başlangıçta 10 test mevcut
  kodda başarısızdı; düzeltme sonrasında yeni testler ve posta regresyonları
  birlikte 36 geçti. Ek incelemede reddedilen çıkış komutundan sonra açık kalan
  bağlantı da düzeltildi; dört bağlantı temizliği testi önce başarısız, sonra
  başarılı oldu. Gerçek sağlayıcı girişinin yapıldığı iddia edilmez.

## Sağlayıcıda salt okunur hazırlık kontrolü

Uygulamanın mevcut güvenli ortam değişkenleriyle backend dizininde çalıştır:

```bash
PYTHONPATH=. python scripts/check_inbound_mail_tls.py
```

Komut TLS sertifikasını ve alan adını doğrular, posta kutusunda giriş yapar ve
oturumu kapatır. İleti göndermez, içerik okumaz, ileti işaretlemez veya silmez.
Kullanıcı/parola ya da ham sağlayıcı hatası yazdırmaz. Çıkış 0 yalnızca doğrulanmış
TLS 1.2/1.3 ve başarılı giriş için döner; hata veya eksik yapılandırma çıkış 1'dir.
Her kullanılan IMAP/POP3 protokolü ve bağlantı yöntemi gerçek ortamda ayrı
doğrulanmalı. Tanı komutunun çalıştırıldığı Python ve CA deposu üretimle aynı olmalı.

Tanı kontrolü başarılı olduktan sonra kontrollü, yetkili test iletisiyle mevcut
uygulamadaki gönderim/alım, ekler ve yeniden senkronizasyon kontrol edilmeli.
Gönderim testleri ayrıca açık yetkilendirme kapsamında yapılmalı. Posta sağlayıcısı
başarılı TLS sunmuyorsa kalıcı çözüm TLS desteği veya desteklenen sağlayıcıya
taşımadır. Sertifika doğrulamasını kapatarak “çözüm” uygulanmamalı.

## www.isgsuite.com.tr için ayrı altyapı işleri

İncelenen `.com.tr` adresi İDEA İSG sayfasını sunuyor. `isg-suite-osgb` master
kodunda restart-setup 403 ile kapalı; `.com.tr` canlı isteğinde zorunlu alanları
isteyen 422 davranışı görüldü. Bunlar aynı yayın sürümü olarak kabul edilmez.
`www.isgsuite.tr/health`, 2 Ekim 2026 07:25 UTC kontrolünde kimliksiz 401 döndü.
`.com.tr` raporundaki 200 health sonucu bu uygulamanın 401 sonucuyla karıştırılmamalı.

VDS SSH hedefi 178.210.168.194:22666 için bu çalışma ortamındaki bağlantı girişimi
“Network is unreachable” hatası verdi. Açık Plesk/DNS yönetim oturumu bulunmadı.
Bu nedenle aşağıdaki sunucu/DNS değişiklikleri uygulanmış değildir:

1. Plesk'te yalnız `isgsuite.com.tr` aboneliğinde HTTP → HTTPS yönlendirmesini
   etkinleştir. Mevcut Nginx/Apache ve sertifika yenileme yöntemini önce incele;
   genel Nginx dosyasını veya diğer alan adlarını değiştirme. HTTP, HTML sunmadan
   301/308 ile kanonik HTTPS adresine gitmeli. TLS ve `/api/v1` isteklerinde
   yönlendirme döngüsü olmamalı; ACME yenilemesi çalışmalı.
2. Kayıt kuruluşundaki NS delegasyonunu bütün yetkili sunucuların SOA ve
   A/MX/TXT/DMARC cevaplarıyla karşılaştır. TXT sorgularındaki SPF var/yok farkını
   ve NS SERVFAIL sonucunu gider. Mevcut DNS kayıtlarının yedeğini al.
3. Bütün gerçek göndericilerin SPF/DKIM hizalamasını ve DMARC rapor alımını
   doğrula. `_dmarc.isgsuite.com.tr` mevcut `p=none` politikasından kontrollü
   yaptırım politikasına geçirilmeli; meşru posta doğrulanmadan reject uygulanmamalı.
   DKIM selector/anahtarı sağlayıcıdan alınmalı, tahmin edilmemeli.
4. NSL-202607 için eski posta sunucusunun gerçek ürünü/sürümü/yamaları ve dışa
   açık servisleri sağlayıcı tarafından doğrulanmalı; uygulama PR'ı EOL posta
   işletim sistemini veya üçüncü taraf CVE'lerini kapatmaz.

## Yayın kararı

PR #473 sağlayıcı doğrulaması tamamlanana kadar taslak kalır. Otomatik merge,
master güncellemesi ve canlı dağıtım yapılmaz. Kullanıcının yeniden onayı değil,
eksik sunucu erişimi ve sağlayıcı test kanıtı bu yayın adımını engelliyor.
Erişim sağlandığında hazırlık kontrolünü çalıştır, gönderim/alımı doğrula,
normal giriş/MFA/PDF/Excel/AI/yedek smoke testlerinden sonra kontrollü yayın yap.
Dokuz NSL bulgusunun tamamının kapandığını bu çalışma iddia etmez.

## Genel regresyon sınırı

Değişiklik öncesindeki hedefli güvenlik koşusu 114 geçti, iki paylaşımlı Redis
testi gerekli Redis servisi bulunmadığından atlandı. Son posta koşusu 36 geçti.
Genel backend koşusu, dış ağ bağlantısını engelleyen yerel test korumasıyla
başlatıldı; buna rağmen mevcut bir testte bulut metadata uç noktasına erişme
girişimi otomatik güvenlik denetimi tarafından reddedildi ve koşu durduruldu.
Bu reddin etrafından dolaşılmadı veya aynı genel koşu yeniden çalıştırılmadı.
Kısmi çıktıda üç başarısızlık işareti var; son traceback/JUnit raporu üretilmediği
için bunların test adları ve nedenleri bu koşudan kesinleştirilemedi. Genel
paketin geçtiği veya bütün regresyonların temiz olduğu iddia edilmez. PR taslak
kalır; metadata erişimi içermeyen posta regresyonları başarıyla tamamlandı.
