# OSGB özel uzaktan eğitim paketi — güvenli ekleme notu

Bu değişiklik mevcut eğitim kayıtlarını, mevcut ortak paketleri, çalışan atamalarını veya video ilerleme kayıtlarını dönüştürmez.

## İzolasyon

- Yeni paket yalnız `osgb_id` kapsamıyla oluşturulur.
- Ortak paketler değişmez; mevcut `fork` davranışı aynen korunur.
- Yeni paket kodu sunucu tarafında `custom--<sector>--<random>` biçimindedir ve diğer OSGB kapsamlarında görünmez.
- Şema değişikliği / migration yoktur.

## Eğitim kuralları

- Yeni paket taslak olarak başlar.
- Zorunlu video izleme eşiği `%100`.
- Sıralı izleme ve sınav kilidi açıktır.
- Final sınavı zorunludur ve geçme puanı `%70`.
- Soru kaynağı yalnız mevcut, gözden geçirilmiş sektör soru paketidir; eşleşme yoksa işlem kapalı kalır.

## Geri alma

Kod geri alınırsa mevcut ana uygulama ve eski paketler eski davranışına döner. Oluşturulmuş özel paket satırları veritabanında kalabilir ancak eski liste uç noktası bilinmeyen paket kodlarını göstermediği için mevcut kullanıcı akışını bozmaz.
