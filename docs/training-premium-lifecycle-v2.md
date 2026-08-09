# Eğitim Premium Yaşam Döngüsü v2

## Amaç

Eğitim bölümünü kullanıcı dostu ve mevzuat odaklı hale getirirken çalışan mevcut eğitim, sınav, PDF, sertifika, sunum, katılım, onay, tarihsel kayıt ve tenant davranışlarını korumak.

## En kritik kural

Çalışan hiçbir özellik kaldırılmaz veya geriye dönük değiştirilmez. Bu paket additive ve feature-flag kontrollüdür. Tarihsel kayıtlar yeniden yazılmaz. Migration yoktur.

## Feature flag

- `TRAINING_PREMIUM_LIFECYCLE_V2_ENABLED=true`
- Acil rollback: `TRAINING_PREMIUM_LIFECYCLE_V2_FORCE_OFF=true`
- Geçiş zamanı: `TRAINING_PREMIUM_LIFECYCLE_V2_AFTER=<ISO-8601>`

Flag kapalıyken mevcut davranış aynen korunur.

## 2026 resmi eğitim kuralları

Kaynak: Çalışma ve Sosyal Güvenlik Bakanlığı / İSGGM Sıkça Sorulan Sorular, 9 Ağustos 2026 tarihinde kontrol edilmiştir.

- İşe başlama eğitimi temel eğitimden ayrıdır; çalışan fiilen işe başlamadan önce verilir.
- İşe başlama eğitimi tüm tehlike sınıflarında yüz yüze ve en az 2 saattir.
- İlk temel eğitim: Az Tehlikeli 8, Tehlikeli 12, Çok Tehlikeli 16 ders saati.
- Tekrar temel eğitimi: tüm tehlike sınıflarında en az 8 ders saati.
- 4. konu başlığı / işe özgü riskler: Az Tehlikeli 2, Tehlikeli 3, Çok Tehlikeli 4 ders saati.
- Bir ders saati 45 dakika ders + 15 dakika ara dinlenmesidir.
- Tehlikeli ve Çok Tehlikeli işyerlerinde 4. konu başlığı yüz yüze yapılır.

Resmi kaynak URL'si uygulama politika API'sinde makine tarafından okunabilir biçimde döndürülür.

## Yaşam döngüsü

Yeni kapsam içindeki kayıtlar için kullanıcı dili:

1. Planlandı
2. Eğitim gerçekleştirilecek
3. Katılım / sonuç bekliyor
4. Sonuçları kesinleştir
5. Belgeye hazır
6. Tamamlandı / arşivlenebilir

Planlama aşamasında `attendance_verified` ve `success_verified` otomatik olarak `false` tutulur. Bu değerler yalnız eğitim sonrası mevcut sonuç kesinleştirme akışı tarafından doğrulanır.

## Eski kayıt koruması

- `TRAINING_PREMIUM_LIFECYCLE_V2_AFTER` öncesindeki kayıtlar mevcut davranışı kullanır.
- Eski sınav snapshot'ları yeniden üretilmez.
- Eski sunum sürümleri ve onayları değiştirilmez.
- Eski PDF/sertifika/katılım belgeleri yeniden numaralandırılmaz.
- DB migration yapılmaz.

## UI ilkeleri

- Teknik terimler yerine kullanıcıya bir sonraki yapılacak işlem gösterilir.
- İşe Başlama Eğitimi ve Bilgi Yenileme Eğitimi seçenekleri açıkça ayrılır.
- Planlama sırasında 'Katılım doğrulandı / Başarı koşulu sağlandı' kutuları kullanıcıdan istenmez.
- Kayıt detayındaki eski `Eğitimi Tamamla` yolu yeni kapsamda güvenli katılım ve sonuç yönetimine yönlendirilir.
- Mevcut React Eğitim sayfası kaldırılmaz; premium yardımcı katman additive olarak çalışır.

## Test kapıları

- Flag OFF legacy parity
- Force-off rollback
- İşe başlama 2 saat / yüz yüze
- İlk temel 8/12/16
- Tekrar temel 8
- Planlama sırasında attendance/success false
- Eski kayıtların davranışı korunuyor
- Güvenli sonuç kesinleştirme akışı bozulmuyor
- Frontend Türkçe, klavye ve mobil davranış testi

## Rollback

İlk işlem:

`TRAINING_PREMIUM_LIFECYCLE_V2_FORCE_OFF=true`

Migration olmadığı için veritabanı downgrade gerekmez. Mevcut eğitim/sınav/PDF/sertifika/sunum kayıtları olduğu gibi kalır.
