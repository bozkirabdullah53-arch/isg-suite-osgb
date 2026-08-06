# NACE Uyumlu Eğitim Sunumu — Uygulama Planı

Epic: #74  
Faz görevleri: #75, #76, #77, #78, #79, #80, #81

## 1. Değiştirilemez koruma sınırı

Aşağıdaki üretim davranışları sunum özelliğinden bağımsız kalacaktır:

- Eğitim oluşturma, NACE seçimi ve eğitim süresi
- Mevcut 20 soruluk sınav üretimi, cevaplama ve puanlama
- Katılım ve başarı sertifikaları
- Mevcut PDF üretim servisleri
- Tarihsel eğitim, sınav, sertifika, onay ve imza kayıtları
- Şirket, işyeri, şube ve rol izolasyonu
- Mevcut object storage local/dual/R2 soyutlaması
- Mevcut frontend navigasyonu ve responsive davranış

Sunum hatası bu işlevlerden hiçbirini bloklamayacaktır.

## 2. Güvenli özellik bayrağı

```text
NACE_TRAINING_PRESENTATION_ENABLED=false
NACE_TRAINING_PRESENTATION_FORCE_OFF=false
```

`FORCE_OFF=true` her durumda önceliklidir. Bayrak kapalıyken sunum paneli görünmez, üretim/indirme uçları çalışmaz ve eski eğitim ekranı aynı kalır.

## 3. Fazlar

### Faz 1 — Salt okunur temel

- Özellik bayrağı
- Ayrı readiness servisi ve API router'ı
- Dondurulmuş NACE snapshot, beş konu, risk etiketleri ve sınav hazırlığı denetimi
- Mevcut Eğitim sayfasına izole, yalnız flag açıkken görünen hazırlık paneli
- Migration, dosya üretimi ve depolama yazması yok

### Faz 2 — İçerik sözleşmesi

Çıktı formatı, slayt sırası, zorunlu bölümler, kaynaklar, görseller, kurumsal şablon ve kalite/fail-closed kuralları uzman onayına sunulur. Koruma metni bu işlevsel içeriği tanımlamadığı için onaydan önce gerçek sunum üretimi açılmaz.

### Faz 3 — Sürümlemeli veri modeli

Her sunum sürümü; kaynak snapshot, şablon sürümü, içerik manifesti, dosya hash'i ve depolama anahtarıyla ayrı kaydedilir. Eski sürüm yerinde değiştirilmez.

### Faz 4 — Üretim ve depolama

Deterministik üretim servisi mevcut `get_object_store()` katmanını kullanır. Uzak depolama hatası yalnız sunumu başarısız bırakır; eğitim/sınav/sertifika devam eder.

### Faz 5 — Arayüz

Mevcut Eğitim sayfası panel, buton, mesaj ve responsive kalıpları kullanılır. Açık `Sunum oluştur` eylemi dışında otomatik üretim yapılmaz.

### Faz 6 — Onay ve tarihsel koruma

Onaylı sürüm değiştirilemez. İçerik değişikliği yeni sürüm ve yeni onay üretir. Mevcut imza/sertifika servisleri değiştirilmez.

### Faz 7 — QA ve cutover

İlk production deploy flag kapalı yapılır. Tam regresyon, görsel QA ve test OSGB kabulü sonrasında kontrollü açılır.

## 4. Zorunlu test matrisi

- Eğitim oluşturma ve NACE seçimi
- 20 soruluk sınav, cevaplama ve puanlama
- Katılım/başarı sertifikaları ve mevcut PDF'ler
- Şirket/işyeri/rol izolasyonu
- Tarihsel kayıtların değişmezliği
- Local/dual/R2 depolama davranışı
- Feature flag açık/kapalı/force-off
- Sunum hatasında çekirdek eğitim akışının devamı
- Masaüstü, laptop, tablet ve mobil
- SQLite, PostgreSQL migration/parity ve frontend E2E

## 5. Stop koşulları

Aşağıdakilerden biri oluşursa riskli workaround uygulanmaz:

- Kaynak sınav/NACE verisi güvenle bağlanamıyorsa
- Migration tarihsel veriyi etkiliyorsa
- Şirket/işyeri izolasyonu garanti edilemiyorsa
- İmza veya sertifika geçerliliği etkileniyorsa
- Ortak CSS/depolama/API değişikliği ilgisiz regresyon oluşturuyorsa

## 6. Rollback

1. `NACE_TRAINING_PRESENTATION_FORCE_OFF=true`
2. Gerekirse sunum router/panel yüklemesini kaldırma
3. Gerekirse önceki production commit'e dönme

Sunum verileri eklemeli olacağı için eğitim, sınav ve sertifika tablolarına rollback yazımı yapılmaz.
