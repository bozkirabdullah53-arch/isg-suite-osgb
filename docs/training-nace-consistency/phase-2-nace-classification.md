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
- `review_required`: Kesin NACE, tehlike sınıfı ve eğitim konuları mevcut; fakat profil için denetlenmiş teknik risk etiketleri eksik. Sistem ana sektör veya metin benzerliğinden risk uydurmaz.
- `legacy_unverified`: Tarihsel kayıtta kesin NACE kimliği bulunmuyor.

## Legacy yaklaşımı

Eski eğitim kayıtlarında yalnız profil kodu varsa sistem kesin NACE tahmin etmez. Bu kayıtlar `legacy_unverified` olarak işaretlenir. Böylece tarihsel kayıtlar silinmez, başka bir NACE'ye yanlış bağlanmaz ve yönetici raporunda açıkça görülebilir.

## Katmanlı sınıflandırma

1. Tam resmî NACE kaydı
2. NACE bölüm kodu ve ana sektör
3. Alt sektör ve faaliyet grubu
4. Kontrollü içerik profili
5. Açık teknik risk etiketleri
6. Tehlike sınıfına bağlı zorunlu süre

Teknik riskler faaliyet adındaki rastlantısal kelimelerle belirlenmez. Yalnız kontrollü profil eşlemesi kullanılabilir. Profil için risk eşlemesi yoksa ana NACE bölümünden genel risk aktarılmaz; kayıt `review_required` olur ve eksiklik snapshot içinde açıkça saklanır.

## Güvenlik ve izolasyon

- Tablo `company_id` taşır.
- PostgreSQL'de RLS ve FORCE RLS uygulanır.
- API erişimi mevcut `ensure_company_access` kontrolünü kullanır.
- Başka şirkete ait eğitim sınıflandırması okunamaz.
- Migration eski eğitimleri topluca tahmin ederek doldurmaz.

## Faz 2 sınırı

Bu faz soru seçme algoritmasını veya sertifika ön kontrolünü henüz değiştirmez. Bunlar sırasıyla Faz 3–5 ve Faz 6–9 kapsamında, bu sınıflandırma snapshot'ı temel alınarak uygulanacaktır. `review_required` ve `legacy_unverified` kayıtların sınav/sertifika üretiminde nasıl bloke edileceği sonraki fazların zorunlu doğrulama katmanında ele alınacaktır. Böylece çalışan PDF ve sınav akışı tek kontrolsüz değişiklikle bozulmaz.
