# Faz 2 — NACE Sınıflandırma ve Tarihsel Snapshot Tasarımı

**Tarih:** 5 Ağustos 2026  
**Dal:** `fix/training-nace-consistency-phase-2`  
**Kapsam:** Kesin NACE kimliği, içerik profili, tehlike sınıfı, konu/risk sınıflandırması ve tarihsel kanıt

## Amaç

Faz 1'de doğrulanan temel hata, seçilen kesin NACE anahtarının geniş bir içerik profiline dönüştürülerek aynı alanda saklanmasıydı. Faz 2 bu iki kavramı ayırır:

- **Kesin NACE kimliği:** resmî katalog anahtarı, NACE kodu ve açıklaması
- **İçerik profili:** eğitim konusu ve teknik risk eşleştirmesinde kullanılan kontrollü profil

Yeni kayıtlar için sınıflandırma yalnız tam katalog anahtarı veya tam NACE koduyla yapılır. Genel sektör adı, metin benzerliği, alias veya `genel_uretim` fallback'i doğrulanmış NACE olarak kabul edilmez.

## Yeni veri yapısı

`training_nace_snapshots` tablosu her eğitim için tek ve değişmez bir sınıflandırma kaydı tutar:

- eğitim, şirket ve işyeri kimliği
- katalog anahtarı
- kesin NACE kodu ve açıklaması
- NACE bölüm/alt sektör/faaliyet grubu
- içerik profil kodu ve adı
- tehlike sınıfı
- beş onaylı sektörel eğitim konusu
- teknik risk etiketleri
- özel riskler
- zorunlu süre
- katalog sürümü ve SHA-256 içerik özeti
- doğrulama durumu
- kaynak sınıflandırmanın JSON kopyası

## Doğrulama durumları

- `verified`: Kesin NACE, tehlike sınıfı, beş eğitim konusu ve kontrollü profil risk eşlemesi mevcut.
- `review_required`: Gelecekte kataloğa yeni bir profil eklenip teknik risk eşlemesi unutulursa kullanılan güvenli blokaj durumu. CI bu durumu başarısızlık kabul eder.
- `legacy_unverified`: Tarihsel kayıtta kesin NACE kimliği bulunmuyor.

## Tam katalog kapsamı

CI denetimi resmî katalogdaki **2.141 NACE satırının tamamını** tek tek çözümler ve aşağıdaki koşulları zorunlu tutar:

- benzersiz tam NACE kodu ve katalog anahtarı
- geçerli tehlike sınıfı
- tam beş kanonik sektörel eğitim konusu
- boş olmayan, açık teknik risk etiketi seti
- `verified` sınıflandırma durumu
- kararlı katalog özeti

Mevcut kapsamda `review_required` kayıt sayısı **0**'dır. Katalogdaki NACE-dışı `genel_uretim` kullanıcı arayüzü seçeneği resmî NACE denetiminden ayrı raporlanır ve yeni eğitim oluşturma şemasında reddedilir.

## Konu tutarlılığı

Aktarım sırasında bazı kesin NACE anahtarlarına başka sektörlerin konu setleri bağlanmıştı. Örnekler:

- hukuk bürosuna atıksu ve kanalizasyon konuları
- güzellik/kuaför profiline restoran ve mutfak konuları
- bilişim/yazılım profiline genel fabrika konuları

Profil düzeyinde onaylanmış düzeltmeler artık bütün ilgili kesin `nace_*` anahtarlarına yayılır. Snapshot içinde:

- kanonik düzeltilmiş konu listesi,
- ham katalog konu listesi,
- iki liste farklıysa `catalog_topics_overridden=true`

birlikte saklanır. Böylece düzeltme yapılırken kaynak veri gizlenmez.

## Teknik risk kataloğu

Daha önce eksik olan 65 içerik profili için teknik riskler ayrı ve sürümlü `training_nace_risk_catalog.py` dosyasında açıkça tanımlandı. Eşleştirmeler yalnız profil başına onaylı beş eğitim konusuna dayanır. Faaliyet açıklamasında kelime arama, ana NACE bölümünden genel risk aktarma veya başka sektör fallback'i kullanılmaz.

Yüksek sonuçlu faaliyetler için ayrıca özel risk kayıtları tutulur; örneğin:

- ergimiş metal ve düşen yük
- buhar bulutu patlaması ve toksik salım
- hidrojen patlaması, kurşun ve asit maruziyeti
- ark parlaması ve elektrik çarpması
- hayvan saldırısı ve zoonotik maruziyet
- yanıcı toz patlaması

## Legacy yaklaşımı

Eski eğitim kayıtlarında yalnız profil kodu varsa sistem kesin NACE tahmin etmez. Bu kayıtlar `legacy_unverified` olarak işaretlenir. Böylece tarihsel kayıtlar silinmez, başka bir NACE'ye yanlış bağlanmaz ve yönetici raporunda açıkça görülebilir.

## Katmanlı sınıflandırma

1. Tam resmî NACE kaydı
2. NACE bölüm kodu ve ana sektör
3. Alt sektör ve faaliyet grubu
4. Kontrollü içerik profili
5. Kanonik beş eğitim konusu
6. Açık teknik risk etiketleri ve özel riskler
7. Tehlike sınıfına bağlı zorunlu süre

## Güvenlik ve izolasyon

- Tablo `company_id` taşır.
- PostgreSQL'de RLS ve FORCE RLS uygulanır.
- API erişimi mevcut `ensure_company_access` kontrolünü kullanır.
- Başka şirkete ait eğitim sınıflandırması okunamaz.
- Migration eski eğitimleri topluca tahmin ederek doldurmaz.
- Snapshot eğitim kaydıyla aynı işlem içinde oluşturulur.

## Doğrulama sonucu

En güncel Faz 2 dalında aşağıdaki CI hatları başarıyla çalıştırılmıştır:

- PostgreSQL Alembic upgrade ve şema parity
- PostgreSQL RLS ve NACE sınıflandırma testleri
- SQLite backend smoke testleri
- tam NACE katalog denetimi
- frontend test, lint, build, E2E ve bağımlılık güvenlik denetimi

## Faz 2 sınırı

Bu faz kesin NACE kimliği, kanonik konu seti ve teknik risk snapshot temelini tamamlar. Soru seçme algoritması ve sertifika ön kontrolü henüz bu snapshot'a bağlanmamıştır. Bunlar sırasıyla Faz 3–5 ve Faz 6–9 kapsamında, bu doğrulanmış veri temelinden beslenecek şekilde uygulanacaktır. Tarihsel `legacy_unverified` kayıtların sınav/sertifika üretiminde nasıl yönetileceği sonraki fazların zorunlu doğrulama katmanında ele alınacaktır.
