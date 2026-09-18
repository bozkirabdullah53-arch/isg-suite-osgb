# İşyeri Yedekleri Tasarımı

## Amaç

İşyeri kullanıcısının sol menüdeki **Yedeklerim** ekranından yalnızca bağlı
olduğu işyerinin verilerinin şifreli yedeğini oluşturabilmesi, geçmiş
yedeklerini görebilmesi ve indirebilmesi; ayrıca sistemin her gece firma
bazında otomatik yedek üretmesidir. Değişiklik mevcut modüllerin davranışını
değiştirmeyecek ve başka işyerlerinin verisini hiçbir yedeğe katmayacaktır.

## Onaylanan ürün kararları

- Otomatik yedek her gece çalışır.
- Otomatik yedekler 30 gün tutulur.
- Kullanıcının elle oluşturduğu yedekler otomatik silinmez.
- İşyeri kullanıcısına canlı geri yükleme yetkisi verilmez.
- Yedek, işyerine ait kayıtları ve bunlara bağlı dosyaları kapsar.
- Mevcut çalışan özellikler korunur; yeni akış özellik bayrağıyla kapatılabilir.

## Mevcut yapı

Uygulamada `EisaArchiveRecord`, `create_tenant_backup`, `/archives` API'leri,
şifreleme, SHA-256 doğrulaması ve güvenli arşiv incelemesi bulunmaktadır.
Mevcut manuel yedekleme **Güvenlik ve Denetim** içinde gösterilir ve v3 formatı
yalnızca bazı alanları dışa aktarır. Bu tasarım mevcut güvenlik altyapısını
yeniden kullanır; ikinci, bağımsız bir yedek formatı oluşturmaz.

## Mimari

### 1. Sürümlemeli firma yedeği

Yedek formatı v4'e yükseltilecek. Her veri alanı açık bir alan kayıt listesinde
tanımlanacak; dinamik tablo taraması yapılmayacak. Her sorgu doğrudan
`company_id == hedef_firma_id` filtresi veya hedef firmaya ait üst kayıtların
kimlikleriyle sınırlandırılacak. Böylece ortak kataloglar ile başka firmaların
kayıtları yanlışlıkla yedeğe giremez.

Bir yedek tek bir işyerini temsil eder. İşyeri ekranından OSGB geneli yedek
üretilemez. Mevcut EİSA/OSGB yönetim yolları korunur ve bu özelliğin dışında
kalır.

### 2. Veri kapsamı

v4 firma yedeği, model mevcutsa aşağıdaki firma alanlarını kapsar:

- firma ve şube bilgileri;
- personel ve personel profil bilgileri;
- eğitimler, katılımcılar, sınav/belge kayıtları ve uzaktan eğitim atamaları;
- sağlık gözetimi kayıtları ve işyerine bağlı sağlık dosyaları;
- risk değerlendirmeleri, tehlikeler, DÖF ve saha denetimleri;
- KKD teslimleri;
- dokümanlar ve işyerine bağlı yüklenen dosyalar;
- iş kazası, ramak kala ve olay kayıtları;
- yıllık plan ve yıllık değerlendirme kayıtları;
- İSG kurulu kayıtları;
- tatbikat, acil durum ekipleri, acil durum planı ve krokiler;
- çalışma izinleri;
- taşeron ve ziyaretçi kayıtları;
- işyerine bağlı görevlendirme ve hizmet sözleşmesi kayıtları.

Her alanın kayıt sayısı `manifest.json` içindeki `domain_counts` bölümüne
yazılır. Şifreli sağlık alanları çözülmeden, veritabanında tutulduğu biçimde
yedeklenir. Parola, erişim anahtarı, oturum belirteci ve sistem sırrı yedeğe
alınmaz.

Bir alanın tablosu veya ilişkisi bu sürümde mevcut değilse yedekleme tümden
başarısız olmaz; alan `not_available` olarak manifestte belirtilir. Buna
karşılık firma kapsamını güvenli biçimde belirleyemeyen bir alan sessizce
eklenmez ve test tamamlanmadan kapsama alınmaz.

### 3. Yedek kaydı ve bütünlük

`EisaArchiveRecord` genişletilerek yedeğin kaynağı (`manual` veya `scheduled`),
durumu (`running`, `completed`, `failed`), tamamlanma zamanı ve hata özeti
tutulacak. Veritabanı geçişi yalnızca nullable/varsayılanlı, geriye uyumlu
sütunlar ekleyecek.

Tamamlanmış arşiv:

- mevcut Fernet tabanlı yedek şifrelemesini kullanır;
- SHA-256 sağlama toplamı taşır;
- geçici dosyaya yazılır ve yalnız başarıdan sonra nihai adına atomik olarak
  taşınır;
- indirme öncesinde dosya varlığı ve sağlama toplamı doğrulanır;
- adında firma kimliği, UTC tarih-saat ve benzersiz ek taşır.

Yarım kalan veya başarısız üretim indirilebilir bir yedek olarak listelenmez.

### 4. Yetkilendirme ve firma izolasyonu

Yedek ekranı yalnızca açıkça bir işyerine bağlı `company_admin` veya
`workplace_manager` hesabına gösterilir. API her istekte kullanıcıdan hedef
firma kimliğini türetir; istemciden gelen firma/OSGB kimliğine güvenmez.

Listeleme, oluşturma, indirme ve içerik inceleme işlemlerinin tamamında:

- kullanıcının aktif olması;
- kullanıcının aktif firmaya bağlı olması;
- arşiv kaydının `company_id` değerinin aynı olması

zorunludur. Başka işyerine ait kayıtlar 403/404 ile reddedilir. İşyeri
kullanıcısına geri yükleme endpoint'i sunulmaz. Mevcut global yönetici yolları
bu değişiklikten etkilenmez.

### 5. Otomatik gece yedeği

Render Cron Job her gece ayrı bir komut çalıştırır. Komut:

1. aktif işyerlerini sayfalı biçimde okur;
2. her firma için son başarılı zamanlanmış yedeği kontrol eder;
3. aynı UTC günü için başarılı yedek varsa tekrar üretmez;
4. firma yedeğini servis hesabı bağlamında, doğrudan firma kimliğiyle oluşturur;
5. sonucu denetim kaydına işler;
6. bir firmanın hatasında diğer firmalarla devam eder;
7. en sonda başarı/başarısızlık sayılarıyla çıkış özeti üretir.

Zamanlama `02:00 Europe/Istanbul` hedefiyle Render'ın UTC cron ifadesine
çevrilir. Yaz/kış saati olmayan Türkiye için bu saat yıl boyunca `23:00 UTC`
olarak çalışır.

Cron, HTTP üzerinden kullanıcı endpoint'ini çağırmaz ve kullanıcı parolası
taşımaz. Aynı firma için eşzamanlı yedek oluşmasını önlemek üzere veritabanı
kilidi/idempotency anahtarı kullanılır.

### 6. Saklama politikası

Gece işi tamamlandıktan sonra yalnızca `source=scheduled`, `status=completed`
ve 30 günden eski firma yedekleri temizlenir. Temizlikte önce arşiv dosyası,
sonra veritabanı kaydı kaldırılır; dosya silinemezse kayıt korunur ve hata
raporlanır.

`source=manual` kayıtları, silinen dosya arşivleri ve başarısızlık denetim
kayıtları bu otomatik temizlikten etkilenmez. Kullanıcı arayüzünde yedek silme
özelliği bu kapsamda eklenmeyecektir.

### 7. Kullanıcı arayüzü

İşyeri sol menüsüne **Yedeklerim** eklenir. Ayrı sayfada:

- son başarılı otomatik yedek zamanı;
- bir sonraki planlanan yedek bilgisi;
- **Şimdi Yedekle** düğmesi;
- durum, kaynak, tarih, boyut ve bütünlük sütunları;
- **İndir** ve salt okunur **İçeriği Gör** işlemleri;
- “otomatik yedekler 30 gün, manuel yedekler süresiz tutulur” açıklaması

yer alır. Başka firma seçici gösterilmez. Küçük ekranlarda mevcut mobil menü
örüntüsü korunur; Yedeklerim masaüstü/tam menüden erişilebilir olur.

Mevcut **Güvenlik ve Denetim** içindeki yedek bölümü tekrar oluşturmamak için
işyeri hesaplarında kaldırılır. OSGB/global yönetici görünümü değişmez.

### 8. Hata davranışı ve mevcut sistemi koruma

- `WORKPLACE_BACKUPS_ENABLED=false` iken yeni menü, API ve cron işlemi kapalıdır.
- Yedekleme hatası ana web uygulamasının başlatılmasını veya isteklerini
  durdurmaz.
- Disk/nesne depolama yetersizliği açık hata üretir; eksik arşiv başarılı
  gösterilmez.
- Bir alanın seri hale getirme hatası yedeği `failed` yapar; eksik olduğu
  saklanan sessiz bir “başarılı” yedek üretilmez.
- Geri yükleme varsayılan kapalı kalır ve bu özellik tarafından açılmaz.

## API taslağı

- `GET /api/v1/workplace-backups` — kullanıcının firmasına ait tamamlanmış ve
  hata durumundaki firma yedekleri.
- `GET /api/v1/workplace-backups/status` — son başarı, çalışan iş ve bir sonraki
  zaman bilgisi.
- `POST /api/v1/workplace-backups` — kullanıcının bağlı firmasını manuel
  yedekler; hedef kimlik kabul etmez.
- `GET /api/v1/workplace-backups/{id}/download` — yalnız aynı firmaya ait,
  tamamlanmış ve bütünlüğü doğrulanmış arşiv.
- `GET /api/v1/workplace-backups/{id}/contents` — manifest özeti; canlı veriye
  yazmaz.

Mevcut `/archives` endpoint'leri geriye uyumluluk için korunur.

## Test stratejisi

### Birim ve servis testleri

- Her yedek alanı yalnız hedef `company_id` kayıtlarını dışa aktarır.
- İki firmalı senaryoda arşivde çapraz firma kimliği/verisi bulunmaz.
- Sağlık şifreli alanı çözülmeden yedeklenir; sırlar yedeğe girmez.
- Manuel/zamanlanmış kaynak ayrımı ve 30 günlük temizlik doğrudur.
- İdempotency aynı firma/gün için ikinci otomatik yedeği engeller.
- Bir firma hatası sonraki firmanın yedeklenmesini engellemez.
- Eksik/geçici dosya başarılı arşiv kaydı üretmez.

### API ve yetki testleri

- İşyeri kullanıcısı kendi yedeğini listeler, oluşturur ve indirir.
- Aynı OSGB içindeki başka işyerinin yedeğine erişemez.
- Firma bağlantısı olmayan kullanıcı yedek ekranına/API'ye erişemez.
- İşyeri kullanıcısı geri yükleme yapamaz.
- Özellik bayrağı kapalıyken menü gizlenir ve yeni API uçları 404 döner.

### Arayüz ve regresyon testleri

- Menü yalnız uygun işyeri rollerinde görünür.
- Firma seçici bulunmaz; manuel yedek sonucu listeye eklenir.
- İndirme ve içerik görüntüleme hata mesajları anlaşılırdır.
- Mevcut eğitim, sağlık, risk, doküman ve güvenlik testleri çalışır.
- Frontend üretim derlemesi ve Render Blueprint doğrulaması geçer.

## Dağıtım

1. Şema geçişi ve kod özellik bayrağı kapalı olarak dağıtılır.
2. API/servis smoke testleri ve tek pilot firma manuel yedeği doğrulanır.
3. `WORKPLACE_BACKUPS_ENABLED=true` ile menü ve manuel akış açılır.
4. Pilot gece işi gözlenir; checksum ve indirilebilirlik doğrulanır.
5. Render Cron Job etkinleştirilir.

Geri alma için özellik bayrağı kapatılır ve cron askıya alınır. Eklenen nullable
sütunlar ile mevcut v3 arşivler yerinde kalır; eski yedek indirme akışı
çalışmaya devam eder.
