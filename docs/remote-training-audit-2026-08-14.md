# Uzaktan Temel İSG Eğitim Modülü Denetimi

Tarih: 14 Ağustos 2026  
İncelenen kaynak: `bozkirabdullah53-arch/isg-suite-osgb` (uzaktan eğitim atama düzeltmesi)
İncelenen canlı adres: <https://www.isgsuite.tr/#m=training>

## Kapsam ve sınır

İnceleme; merkezi video katalogu, firma programı snapshot'ı, çalışan ataması,
video ilerleme/sınav kapıları, sertifika akışı, responsive kullanım ve üretim
video işleme bağımlılıklarını kapsar. Canlı tarayıcı oturumunda giriş ekranı
görüldü; kullanıcı hesabı/parolası istenmedi ve canlı veride işlem yapılmadı.
Kullanıcının gönderdiği yetkili ekran görüntüsü, yönetici görünümünün görsel
kanıtı olarak ayrıca dikkate alındı.

## Bulgular

### 1. Firma ve sektör atama ekranı dağıtım kapısına gereksiz bağlanmıştı — yüksek öncelik

Merkezi katalog görünür durumdayken şirket ve sektör eşleştirmesi yöneticinin
seçimine bırakılmak istenmesine rağmen firma atama adımı ayrı bir dağıtım
kapısına bağlıydı. Bu, yayımlanmış paketi seçilen firmaya hazırlamayı
engelliyordu.

Uygulanan düzeltme:

- Firma ve sektör eşleştirmesi artık yöneticinin seçtiği firma + yayımlanmış
  sektör paketi üzerinden ilerliyor; otomatik firma ataması yapılmıyor.
- Meta endpoint'i dağıtım durumunu, izinli paket kodlarını ve allowlist bilgisinin
  yapılandırılıp yapılandırılmadığını güvenli biçimde bildiriyor; şirket ID'leri
  dışarı açılmıyor.
- Arayüzde “Kontrollü pilot kapalı” yerine firma bazlı manuel atama açıklaması
  gösteriliyor.
- Tüm katalog paketleri dağıtıma açık olsa bile yalnızca yöneticinin seçtiği
  firmaya hazırlanıyor; çalışanlara otomatik atama yapılmıyor.

### 2. Yedi katalog paketi yanlışlıkla `common` sektörüne düşüyordu — yüksek öncelik

Gıda, lojistik, kimyasal/boya, maden/agrega, yol/asfalt/altyapı,
ofis/genel işyerleri ve yüksekte çalışma paketleri materyalize edilirken
`common` sektörüne bağlanabiliyordu. Bunun sonucu çalışan kapsamı, sınav soru
filtreleri, raporlar ve pilot paket kimliği yanlış olabilirdi.

Uygulanan düzeltme:

- Sektör kataloğu ve paket-sektör eşleşmeleri tamamlandı.
- `0094_repair_catalog_sector2` migrasyonu eklendi.
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

Bu çalışma; migration, API dağıtım kapısı ve uzaktan eğitim bileşeninin CSS/UI
katmanı ile sınırlıdır. Temel eğitim, eski programlar, mevcut çalışan
atamaları, sertifika/PDF akışları ve legacy ilerleme davranışı için silme veya
geriye dönük yeniden yazma yapılmamıştır. Firma ve sektör dağıtımı manuel
seçime bağlıdır; canlı çalışanlara otomatik atama başlamaz.

## Doğrulama

- Uzaktan eğitim ve legacy eğitim yaşam döngüsü regresyon paketi: `42 passed`.
- Frontend production build: başarılı (`vite build`).
- Python syntax/compile kontrolü: başarılı.
- Alembic head kontrolü: tek head, `0094_repair_catalog_sector2`.
- Canlı ortamda oturum açma bilgisi olmadığı için yetkili görsel smoke test
  çalıştırılmadı; canlı veride hiçbir işlem yapılmadı.

## Manuel firma/sektör atama kontrol listesi

1. Migration'ı staging'de çalıştırın ve yalnızca beklenen taslak snapshot'ların
   sektörlerinin değiştiğini doğrulayın.
2. `REMOTE_BASIC_OHS_STRICT_POLICY_ENABLED=true` ve dağıtılacak paket kodlarını
   Render ortamında açıkça tanımlayın; `PILOT_COMPANY_IDS` boşsa firma seçimini
   yönetici yapar. Bu ayar otomatik firma ataması yapmaz.
3. Bir çalışan hesabıyla video başlatma, ileri sarma, sekme yenileme, eksik
   video, sınav başarısızlığı, tekrar deneme ve sertifika üretimini uçtan uca
   test edin.
4. Yönetici önce firmayı, sonra sektör paketini seçer; ardından çalışanları
   ayrı çalışan atama ekranından eşleştirir.
