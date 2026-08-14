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

Canlı salt-okunur kontrolünde ERDİL AKÜ için iki ayrı firma programı bulundu:
`Ortak Temel İSG` (program 4) ve `Akü-Batarya` (program 5). İkisinde de çalışan
ataması yoktu. Soru bankasında ortak soru ve Akü/NACE kapsamlı soru ayrı ayrı
mevcuttu; Akü programına ortak sorunun bağlanmış olması ve ortak sektörün
seçili kalması da bu incelemede doğrulandı. Canlı veriye düzeltme yazılmadı.

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

### 7. Katalogdan gelen Akü-Batarya kartı ortak kapsamı yanlış kilitliyordu — kritik

Canlı ekran görüntüsünde Akü-Batarya programında `Temel Ortak İSG` kutusu
seçili ve kilitli görünüyordu. Programın bölümleri Akü-Batarya sektöründe
olduğu için yayımlama kontrolü ortak sektörde video arıyor ve
`Seçilen sektörlerde yayımlanmış video bulunmuyor: Temel Ortak İSG` hatası
üretiyordu. Bu, çalışan atamasından önceki firma snapshot/kapsam katmanında
oluşan bir hataydı; çalışan ekranının sorunu değildi.

Uygulanan düzeltme:

- Merkezi katalogdan kopyalanan programın kapsamı paket kodundan tek ve sabit
  sektör olarak hesaplanıyor. `Akü-Batarya` yalnızca `battery`, `Ortak Temel
  İSG` yalnızca `common` kapsamıdır.
- Katalog programına başka sektör seçme, yanlış sektörde bölüm oluşturma veya
  yanlış kapsamlı video içi soru ekleme API tarafından reddediliyor. Elle
  oluşturulmuş eski programların çoklu sektör davranışı korunuyor.
- Sınav soru bağlantısı da program kapsamına göre denetleniyor. Ortak kapsamlı
  soru Akü-Batarya sınavına bağlanamıyor; eski yanlış bağlantılar silinmiyor,
  yayımlama öncesi açık hata ile durduruluyor.
- Yönetici ekranına bağlı soruları tek tek çıkarma düğmesi eklendi. Atama
  yapılmış veya yayımlanmış programlarda bu işlem kilitli kalıyor.
- `0094_repair_catalog_sector2` artık tüm bilinen katalog paketlerini kapsıyor;
  yalnızca atanmamış taslak/inceleme snapshot'larının kapsamını düzeltir.

## Koruma kararı

Bu çalışma; migration, API dağıtım kapısı ve uzaktan eğitim bileşeninin CSS/UI
katmanı ile sınırlıdır. Temel eğitim, eski programlar, mevcut çalışan
atamaları, sertifika/PDF akışları ve legacy ilerleme davranışı için silme veya
geriye dönük yeniden yazma yapılmamıştır. Firma ve sektör dağıtımı manuel
seçime bağlıdır; canlı çalışanlara otomatik atama başlamaz.

## Doğrulama

- Uzaktan eğitim hedef/regresyon paketi: `16 passed`.
- Frontend birim testleri: `22 dosya / 98 test passed`.
- Frontend production build: başarılı (`vite build`).
- Frontend hedef dosyalar için ESLint: hatasız.
- Python syntax/compile kontrolü: başarılı.
- Alembic head kontrolü: tek head, `0094_repair_catalog_sector2`.
- 0094 migration SQLite smoke testi: başarılı; atanan ve elle değiştirilmiş
  programlar korunuyor.
- Canlı ortamda oturum açma bilgisi olmadığı için yetkili görsel smoke test
  çalıştırılmadı; canlı veride hiçbir işlem yapılmadı.

Tam backend suite denemesinde uzaktan eğitim ve ilgili yaşam döngüsü testleri
geçti. Geniş test grubunun bazı dosyaları uygulama assertion'ı değil, testlerin
aynı süreçteki model-import sırasına bağlı `training_presentation_versions`
eksik tablo kurulum hatası üretti; bu nedenle canlıya alma kararı bu sonuç
temizlenmeden verilmemelidir. Etkilenen dosyalar uzaktan eğitim kodundan
bağımsız mevcut test-harness konusudur.

## Manuel firma/sektör atama kontrol listesi

1. Migration'ı staging'de çalıştırın ve yalnızca beklenen taslak snapshot'ların
   sektörlerinin değiştiğini doğrulayın.
2. `REMOTE_BASIC_OHS_STRICT_POLICY_ENABLED=true` ve dağıtılacak paket kodlarını
   Render ortamında açıkça tanımlayın; `PILOT_COMPANY_IDS` boşsa firma seçimini
   yönetici yapar. Bu ayar otomatik firma ataması yapmaz.
3. Katalogdan gelen her kartta yalnızca kartın kendi sektörü seçili/aktif
   olmalıdır. Akü-Batarya kartında ortak eğitim kutusu seçilmemelidir; ortak
   eğitim ayrı karttan hazırlanır.
4. Soru bankasından yayımlanmış doğru kapsam sorusunu bağlayın. Yanlış bağlı
   eski soru varsa `Sınavdan çıkar` ile kaldırın; sonra programı yayımlayın.
5. Yönetici önce firmayı, sonra sektör paketini seçer; ardından çalışanları
   ayrı çalışan atama bölümünden eşleştirir. Çalışan hesabı açıldıktan sonra
   çalışan yalnızca `Çalışan Eğitimleri` sayfasında kendisine atanmış tüm
   eğitimleri, tarihleri, videoları, sınavı ve sertifikayı görür. Atama sırasında
   son tarih alanı doldurulursa yaklaşan/bugün/geçmiş filtreleri çalışır.
6. Bir çalışan hesabıyla video başlatma, ileri sarma, sekme yenileme, eksik
   video, sınav başarısızlığı, tekrar deneme ve sertifika üretimini uçtan uca
   test edin.
