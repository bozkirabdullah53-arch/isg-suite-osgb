# Uzaktan Temel İSG Eğitim Modülü Denetimi

Tarih: 14 Ağustos 2026  
İncelenen kaynak: `bozkirabdullah53-arch/isg-suite-osgb` (`master`, `194d56b`)  
İncelenen canlı adres: <https://www.isgsuite.tr/#m=training>

## Kapsam ve sınır

İnceleme; merkezi video katalogu, firma programı snapshot'ı, çalışan ataması,
video ilerleme/sınav kapıları, sertifika akışı, responsive kullanım ve üretim
video işleme bağımlılıklarını kapsar. Canlı tarayıcı oturumunda giriş ekranı
görüldü; kullanıcı hesabı/parolası istenmedi ve canlı veride işlem yapılmadı.
Kullanıcının gönderdiği yetkili ekran görüntüsü, yönetici görünümünün görsel
kanıtı olarak ayrıca dikkate alındı.

## Bulgular

### 1. Kontrollü pilot kapalıyken yarım iş akışı oluşuyordu — yüksek öncelik

Üretimde merkezi katalog görünür durumdayken strict pilot politikası kapalıdır.
Önceki arayüz “paket yayımlandı, firmaya atanabilir” mesajı veriyordu; sonraki
firma programı yayımlama/çalışan atama adımı ise pilot kapalı olduğu için
reddediliyordu. Bu, yöneticiyi başarı sanılan ama kullanılamayan bir ara duruma
getiriyordu.

Uygulanan düzeltme:

- API artık pilot kapalıyken merkezi paketten firma snapshot'ı üretmiyor.
- Meta endpoint'i pilot durumu, izinli paket kodlarını ve allowlist bilgisinin
  yapılandırılıp yapılandırılmadığını güvenli biçimde bildiriyor; şirket ID'leri
  dışarı açılmıyor.
- Arayüz izinli/kapalı paketleri ayırıyor ve doğru kullanıcı mesajı veriyor.
- Strict pilot üretimde hâlâ kapalı bırakıldı; mevcut operasyon davranışı
  kendiliğinden açılmadı.

### 2. Yedi katalog paketi yanlışlıkla `common` sektörüne düşüyordu — yüksek öncelik

Gıda, lojistik, kimyasal/boya, maden/agrega, yol/asfalt/altyapı,
ofis/genel işyerleri ve yüksekte çalışma paketleri materyalize edilirken
`common` sektörüne bağlanabiliyordu. Bunun sonucu çalışan kapsamı, sınav soru
filtreleri, raporlar ve pilot paket kimliği yanlış olabilirdi.

Uygulanan düzeltme:

- Sektör kataloğu ve paket-sektör eşleşmeleri tamamlandı.
- `0094_repair_remote_catalog_sector_scope_v2` migrasyonu eklendi.
- Migration yalnızca atanmamış, `draft`/`ready_for_review` durumundaki ve
  yöneticinin özel sektör düzenlemesi bulunmayan katalog snapshot'larını ele
  alır. Yayımlanmış, atanmış veya elle değiştirilmiş programlara dokunmaz.
- Mevcut legacy programlar ve çalışan geçmişi değiştirilmez.

### 3. Üretimde `ffprobe` garantisi yoktu — yüksek öncelik

Video işleme servisi süresini `ffprobe` ile okuyor. Araç yoksa video süresi
`0` kalabiliyor; bu da yayımlama ve zorunlu ilerleme kaydının daha sonra
“video süresi eksik” hatası vermesine neden olabiliyor.

Uygulanan düzeltme: Docker tabanlı root/backend imajlarına `ffmpeg` kurulumu
eklendi. Render native Python runtime'ı `ffmpeg`'i build ve runtime aşamalarında
zaten sağladığı için mevcut Render build komutu değiştirilmedi. Böylece
`ffprobe` video yükleme, süre hesabı, yayımlama ve çalışan ilerlemesi için
üretim ortamında bulunur.

### 4. Yönetici ekranında native/default kontroller ve dar ekran taşması vardı — orta öncelik

Gönderilen ekran görüntüsünde `Paketleri yenile` gibi kontroller tarayıcının
default görünümünde kalıyor; geniş minimum kolonlar tablet/dar ekranda yatay
taşma riski oluşturuyordu. Eğitim yönetimi birden fazla işlem alanını aynı
ekranda gösterdiği için durum bilgisi de kolayca kaybolabiliyordu.

Uygulanan düzeltme: modüle özel CSS katmanı, tutarlı buton/form kontrolleri,
focus görünürlüğü, durum/uyarı renkleri, 900px ve 600px kırılımında tek kolona
inen grid'ler, tablo/video taşma koruması ve dört adımlı akış göstergesi eklendi.

### 5. Yönetici ve çalışan bağlamları aynı seviyede karışıyordu — orta öncelik

Yönetici kullanıcıda çalışan panelinin otomatik ve açık biçimde aşağıda
görünmesi, “kendi eğitimim” ile “firma yönetimi” görevlerini karıştırıyordu.

Uygulanan düzeltme: yöneticinin çalışan görünümü erişilebilir bir “önizleme /
kendi eğitimlerim” açılır alanına taşındı; çalışan rolünde panel doğrudan
görünür kaldı. Yetkisi/eşleştirmesi olmayan kullanıcıya boş panel yerine açık
durum mesajı gösteriliyor.

### 6. Başarı mesajları ekran okuyucuya bildirilmemişti — düşük/orta öncelik

Yükleme, paket ve program işlemlerinin başarı mesajları görsel metin olarak
güncelleniyor ancak durum değişimi yardımcı teknolojilere açık değildi.

Uygulanan düzeltme: ilgili mesaj alanlarına `role="status"` ve
`aria-live="polite"` eklendi; hata alanları mevcut `alert` davranışıyla
korundu.

## Koruma kararı

Bu çalışma; migration, API pilot kapısı ve uzaktan eğitim bileşeninin CSS/UI
katmanı ile sınırlıdır. Temel eğitim, eski programlar, mevcut çalışan
atamaları, sertifika/PDF akışları ve legacy ilerleme davranışı için silme veya
geriye dönük yeniden yazma yapılmamıştır. Pilot kapısı varsayılan olarak
kapalı tutulduğu için canlı çalışanlara otomatik atama başlamaz.

## Doğrulama

- Uzaktan eğitim ve legacy eğitim yaşam döngüsü regresyon paketi: `42 passed`.
- Frontend production build: başarılı (`vite build`).
- Python syntax/compile kontrolü: başarılı.
- Alembic head kontrolü: tek head, `0094_repair_remote_catalog_sector_v2`.
- Canlı ortamda oturum açma bilgisi olmadığı için yetkili görsel smoke test
  çalıştırılmadı; canlı veride hiçbir işlem yapılmadı.

## Pilot açma öncesi kontrol listesi

1. Migration'ı staging'de çalıştırın ve yalnızca beklenen taslak snapshot'ların
   sektörlerinin değiştiğini doğrulayın.
2. `REMOTE_BASIC_OHS_STRICT_POLICY_ENABLED=true` değerini önce tek pilot
   paket/allowlist şirketi için açın; acil kapatma için mevcut `FORCE_OFF`
   anahtarını kullanın.
3. Bir çalışan hesabıyla video başlatma, ileri sarma, sekme yenileme, eksik
   video, sınav başarısızlığı, tekrar deneme ve sertifika üretimini uçtan uca
   test edin.
4. Pilot doğrulanmadan diğer paket kodlarını allowlist'e eklemeyin.
