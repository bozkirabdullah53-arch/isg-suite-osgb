# NACE Eğitim Sunumu İçerik ve Şablon Sözleşmesi v1

Bağlı epic: #74  
Faz: #76  
Makine doğrulama alt görevi: #83

## 1. Karar

Ana çıktı **PPTX**, yardımcı çıktı **PDF** olacaktır.

- PPTX, eğitmenin düzenleyebildiği sunum dosyasıdır.
- PDF, aynı değişmez içerik manifestinden ayrı bir yerel renderer ile oluşturulur.
- Render ortamında LibreOffice, Microsoft Office veya sunucu tarafı Office dönüşümü kullanılmaz.
- PPTX ve PDF farklı içerik üretmez; aynı manifest, aynı kaynak kimlikleri ve aynı içerik hash'i kullanılır.
- Faz 2 dosya üretmez. Gerçek renderer Faz 4 (#78) kapsamındadır.

## 2. Güncel mevzuat tabanı

Sözleşme hazırlanırken 2 Nisan 2026 tarihli ve 33212 sayılı Resmî Gazete'de yayımlanan güncel **Çalışanların İş Sağlığı ve Güvenliği Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik** esas alınmıştır.

Kaynak kayıtları:

- `tr-law-6331`: 6331 sayılı İş Sağlığı ve Güvenliği Kanunu
- `tr-training-regulation-2026`: 2 Nisan 2026, 33212 sayılı Resmî Gazete
- `csgb-training-faq-2026`: Bakanlığın güncel eğitim uygulama açıklamaları
- `csgb-training-guide`: İSGGM eğitim uygulama rehberi kayıt noktası

Mevzuat veya resmi rehber kaydı değişirse mevcut sunumlar yerinde değiştirilmez. Yeni sözleşme/şablon sürümü oluşturulur.

## 3. Hedef uzunluk

- Hedef: **22 slayt**
- Alt sınır: **18 slayt**
- Üst sınır: **32 slayt**
- Görüntü oranı: **16:9**
- Slayt başına en çok 6 madde
- Madde başına en çok 18 kelime
- Her slaytta konuşmacı notu ve kaynak alt bilgisi

Manifest önizleme servisi, beş işe özgü konu için birer slayt oluşturduğu standart senaryoda **21 slayt** üretir. Sektörün karmaşıklığına göre konu/risk slaytları artırılabilir; üst sınır aşılamaz.

## 4. Zorunlu bölüm sırası

1. Kapak
2. Eğitimin amacı ve öğrenme hedefleri
3. Mevzuat ve sorumluluklar
4. İşyeri faaliyeti ve NACE kimliği
5. Eğitim planı ve süre
6. Temel İSG ilkeleri
7. İşe ve işyerine özgü beş konu
8. Teknik ve özel riskler
9. Kontrol tedbirleri ve güvenli çalışma
10. Kişisel koruyucu donanım
11. Acil durum, tahliye ve bildirim
12. Bilgi kontrolü ve değerlendirme
13. Özet ve güvenli davranışlar
14. Kaynaklar ve sürüm bilgisi

## 5. Kaynak önceliği

İzin verilen kaynaklar:

1. Eğitim kaydına ait dondurulmuş ve `verified` NACE snapshot
2. Snapshot içindeki tam beş eğitim konusu
3. Kontrollü teknik risk ve özel risk kayıtları
4. Mevcut onaylı 5 temel + 15 işe özgü soru bankası/sınav hazırlığı
5. Resmî mevzuat
6. ÇSGB/İSGGM resmî rehber ve açıklamaları
7. Uzman onaylı işyerine özel kullanıcı girdisi

Yasaklanan kaynaklar:

- Başka sektörden soru, konu veya risk fallback'i
- Legacy sektör değerinden NACE tahmini
- Kaynaksız teknik iddia
- Modelin tek başına oluşturduğu doğrulanmamış iddia
- İncelenmemiş internet içeriği

## 6. Fail-closed kuralları

Aşağıdaki durumlarda tam manifest veya dosya üretimi durur:

- Özellik kapalıysa
- Persisted ve verified NACE snapshot yoksa
- NACE kodu veya açıklaması eksikse
- Tam beş eğitim konusu yoksa
- Teknik risk etiketi yoksa
- 5 temel + 15 işe özgü sınav içeriği hazır değilse
- Resmî kaynak kaydı eksik/onaysızsa
- Başka sektör fallback'i tespit edilirse
- Kaynaksız iddia varsa
- Manifest hash'i geçersizse

Sunum hatası; eğitim oluşturma, sınav, puanlama, PDF veya sertifika akışını engellemez.

## 7. İşyerine özel alanlar

Aşağıdaki alanlar genel NACE kataloğundan uydurulmaz:

- Şirket/OSGB logosu
- Toplanma yeri
- Acil durum telefonları
- İşyerinde kullanılan gerçek KKD
- İş ekipmanı ve makine listesi
- İşyerine özel güvenli çalışma talimatları
- Yerleşim, tahliye ve saha fotoğrafları

Bu alanlar boşsa manifestte `approval_required` ve yer tutucu olarak kalır. Uzman onayı olmadan yayımlanmaz.

## 8. Görsel ve telif politikası

- Mevcut OSGB renkleri, tipografisi ve tasarım hiyerarşisi kullanılır.
- Şirket veya OSGB tarafından yüklenen logo kullanılabilir.
- Varsayılan olarak uzaktan görsel indirilmez.
- Stok veya yapay zekâ ile üretilmiş görsel otomatik eklenmez.
- Kullanılan her görsel için kaynak/lisans bilgisi tutulur.
- Neon renk, ilgisiz karanlık tema, ağır animasyon ve lisanssız görsel yasaktır.

## 9. Sürüm ve hash

Sözleşme sürümü:

`nace-training-presentation-contract-v1`

Şablon sürümü:

`osgb-training-presentation-template-v1`

Manifest hash girdileri:

- Sözleşme ve şablon sürümü
- Dondurulmuş NACE snapshot
- Beş eğitim konusu
- Teknik ve özel riskler
- Uzman onaylı işyeri girdileri
- Resmî kaynak kayıtları
- Sıralı slayt manifesti

Hash algoritması SHA-256'dır. Üretilmiş veya onaylanmış manifest yerinde değiştirilmez; değişiklik yeni sürüm oluşturur.

## 10. Faz 2 API sınırı

Salt okunur uçlar:

- `GET /api/v1/trainings/presentation-contract`
- `GET /api/v1/trainings/{training_id}/presentation-readiness`
- `GET /api/v1/trainings/{training_id}/presentation-manifest-preview`

Bu uçlar veritabanına yazmaz, dosya oluşturmaz ve object storage kullanmaz.

## 11. Faz 2 tamamlanma koşulu

- Sözleşme JSON'u makine tarafından doğrulanır.
- Güncel 2026 resmi kaynak kaydı bulunur.
- Verified örnek NACE için deterministik manifest oluşturulur.
- Legacy kayıt için manifest oluşturulmaz.
- Başka sektör fallback'i kullanılmaz.
- Feature flag varsayılan kapalı kalır.
- Mevcut eğitim, sınav, PDF ve sertifika regresyonları geçer.
