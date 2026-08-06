# Faz 5 — Eğitim Sayfası Sunum Paneli

Bağlı epic: #74  
Görev: #79

## Amaç

NACE eğitim sunumu işlevini mevcut Eğitim sayfasına yeni bir ana menü veya ayrı uygulama eklemeden, kayıtlı eğitim çıktılarının hemen altında izole bir panel olarak bağlamak.

## Görünürlük

Panel yalnız aşağıdaki iki koşul birlikte sağlandığında görünür:

- Kayıtlı bir eğitim ID'si vardır.
- `NACE_TRAINING_PRESENTATION_ENABLED=true` ve force-off kapalıdır.

Feature flag kapalıysa panel DOM'a eklenmez. Mevcut eğitim formu, katılımcılar, 20 soruluk sınav, sertifika PDF ve katılım PDF düğmeleri aynen kalır.

## Panel içeriği

Panel aşağıdaki bilgileri gösterir:

- Exact NACE kodu ve açıklaması
- Tehlike sınıfı
- Doğrulanmış NACE snapshot durumu
- Tam beş işe özgü konu durumu
- Teknik risk durumu
- 5 temel + 15 işe özgü sınav hazırlığı
- İçerik/şablon sözleşmesi
- PPTX/PDF renderer durumu
- Son sunum sürümü ve dosya durumları
- Son beş sürümün salt okunur geçmişi

## Kullanıcı akışı

### 1. İçerik önizlemesi

`İçerik Önizlemesi` düğmesi salt okunur manifesti açar.

- Dosya üretmez.
- Veritabanına yazmaz.
- Slayt sırasını ve uzman onayı gereken slaytları gösterir.
- Manifest hash'inin ilk bölümünü gösterir.
- ESC, kapatma düğmesi veya arka alana tıklama ile kapanır.
- Kapanınca klavye odağı önceki düğmeye döner.

### 2. İlk taslak

Sunum sürümü yoksa `Sunum Taslağı Oluştur` görünür.

Taslak yalnız dondurulmuş manifest ve kaynak snapshot kaydıdır. PPTX/PDF henüz üretilmez.

### 3. Dosya üretimi

Taslak veya başarısız sürüm için:

`PPTX + PDF Oluştur`

veya

`PPTX + PDF Yeniden Oluştur`

kullanılır.

İşlem sırasında yalnız ilgili düğmeler pasifleşir. Eğitim sayfası yenilenmez; seçili firma, katılımcılar, NACE ve form alanları kaybolmaz.

### 4. İndirme

Başarılı sürümde:

- `PPTX İndir`
- `PDF İndir`

butonları görünür. Dosya boyutu düğmede gösterilir. İndirme backend'deki şirket erişimi ve SHA-256 doğrulamasından sonra başlar.

### 5. Yeni sürüm

Başarılı, onaylı veya arşivlenmiş sürüm yerinde değiştirilmez. `Yeni Sürüm Oluştur` yeni değişmez manifest snapshot'ı oluşturur.

## Hata davranışı

Sunum API'si veya üretim işlemi hata verirse:

- Hata yalnız panel içinde gösterilir.
- Eğitim formu kapanmaz.
- Sayfa yenilenmez.
- Sınav/PDF/sertifika düğmeleri pasifleşmez.
- Firma, personel ve NACE seçimi korunur.
- Panel endpointi kullanılamıyorsa panel sessizce kaldırılır; ana Eğitim sayfası çalışmaya devam eder.

## Responsive ve erişilebilirlik

- Panel genişliği hiçbir zaman kapsayıcısını aşmaz.
- 900 piksel altında kontroller tek sütuna geçer.
- 760 piksel altında eylemler iki sütuna, 520 piksel altında tek sütuna geçer.
- Düğmeler en az 44 piksel yüksekliğindedir.
- Uzun NACE ve hata metinleri satır kırar.
- Sürüm geçmişi mobilde tek sütundur.
- Önizleme penceresi en fazla ekranın yüzde 92 yüksekliğini kullanır.
- Mobilde yatay sayfa kaydırması oluşturmaz.
- Klavye odağı görünürdür; önizleme ESC ile kapanır.
- Hareket azaltma tercihi desteklenir.

## Performans koruması

Eğitim sayfası dinamik olduğu için panel bir `MutationObserver` ile bağlanır. Panel kendi DOM'unu güncellediğinde yeniden çizim döngüsü oluşmaması için veri ve işlem durumundan bir render imzası üretilir. İmza değişmemişse DOM yeniden yazılmaz.

Readiness ve sürüm cevapları eğitim ID'si bazında önbelleğe alınır. Kullanıcı eyleminden sonra yalnız ilgili kayıt zorla yenilenir.

## Testler

- Feature flag kapalı panel görünmezliği
- Renderer ve gerçek blocker normalizasyonu
- İlk taslak, render, yeniden render, indirme ve yeni sürüm eylem kuralları
- API çağrı sayısı ve MutationObserver render döngüsü
- Mevcut sertifika düğmesinin korunması
- Manifest önizleme açma/kapatma
- 390×844 mobil görünüm
- Yatay taşma kontrolü
- 44 piksel dokunma hedefleri
- Frontend test, lint, build ve Playwright E2E
- Backend readiness ve bütün mevcut eğitim regresyonları

## Rollback

Anında görünürlük ve yeni işlem kapatma:

`NACE_TRAINING_PRESENTATION_FORCE_OFF=true`

Panel API'den `visible:false` aldığı için DOM'dan kaldırılır. Mevcut eğitim akışı eski görünümüyle devam eder.

Kod rollback gerektiğinde yalnız sunum readiness bridge/logic/CSS değişiklikleri ve readiness v3 güncellemesi geri alınır. Veri migrationı yoktur; Faz 3'te oluşmuş tarihsel sürümler backend üzerinden korunur.

## Production geçişi

Faz 5 deployunda feature flag yine kapalı kalır. Arayüz kodu production'a kurulacak fakat kullanıcıya görünmeyecektir. Kontrollü açılış ve kullanıcı kabulü Faz 7 kapsamındadır.
