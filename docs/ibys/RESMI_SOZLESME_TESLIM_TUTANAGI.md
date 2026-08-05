# İBYS Resmî Veri Sözleşmesi ve Test Erişimi Teslim Tutanağı

Bu tutanak, İSGGM tarafından teknik doküman/test erişimi sağlandığında doldurulur. Boş alanlar tahmin veya genel bilgiyle tamamlanmaz.

## 1. Teslim bilgileri

- Teslim tarihi: `...`
- Teslim eden Bakanlık birimi/yetkilisi: `...`
- Teslim alan şirket/yetkili: `...`
- Doküman adı: `...`
- Doküman sürümü: `...`
- Doküman tarihi: `...`
- Dosya SHA-256: `...`
- Gizlilik sınıfı / paylaşım kısıtı: `...`

## 2. Teknik içerik kontrolü

| Kontrol | Var/Yok | Sürüm / açıklama |
|---|---|---|
| Veri-seti kataloğu |  |  |
| Alan isimleri ve veri türleri |  |  |
| Zorunlu/opsiyonel alanlar |  |  |
| Kod listeleri |  |  |
| Test endpointleri |  |  |
| Production endpointleri |  |  |
| Kimlik doğrulama yöntemi |  |  |
| Sertifika / IP izin prosedürü |  |  |
| İstek örnekleri |  |  |
| Yanıt örnekleri |  |  |
| Hata/ret kodları |  |  |
| Mükerrer kayıt/idempotency kuralı |  |  |
| Paket boyutu ve kayıt limiti |  |  |
| Timeout/retry kuralı |  |  |
| Durum sorgulama/mutabakat yöntemi |  |  |
| Loglama ve kişisel veri kısıtları |  |  |
| Kabul test senaryoları |  |  |

## 3. Uyarlama kararları

- Yeni profil sürümü: `official-...`
- Eski aday profil korunacak mı: `Evet`
- Geriye uyumluluk planı: `...`
- Test ortamı feature flag adı: `...`
- Production açılış feature flag adı: `...`
- Credential saklama yöntemi: `Render secret / kurumun belirlediği yöntem`
- Rollback yöntemi: `...`

## 4. Güvenlik kontrolleri

- Secret değerleri GitHub’a yazılmayacak.
- İstek/yanıt loglarında TCKN, sağlık içeriği ve credential bulunmayacak.
- Test verisi gerçek kişisel veri içermeyecek veya Bakanlıkça onaylı anonim veri kullanılacak.
- Production gönderimi ayrı feature flag ve rol kontrolü olmadan açılamayacak.
- İlk canlı gönderimden önce kayıt bazlı snapshot ve mutabakat planı onaylanacak.

## 5. İmza

Teslim eden: `...`

Teslim alan: `...`

Teknik sorumlu: `...`
