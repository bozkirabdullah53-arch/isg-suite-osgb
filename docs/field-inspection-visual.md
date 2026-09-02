# GPS'li görsel saha denetimi

Bu modül mevcut hızlı `/risks` saha akışına eklenmiştir. Yeni kayıtlar
`/api/v1/field-inspections` uçlarında ve `field_*` tablolarında tutulur;
mevcut risk, ziyaret, fotoğraf ve rapor kayıtları taşınmaz.

## Güvenli açılış

Önce `0105_visual_field_inspections` Alembic migration'ı uygulanır. Uygulama
başlangıcında 75 sistem tehlike kategorisi eksikse idempotent biçimde eklenir.
Üretimde gerçek sırlar yalnızca secret/environment olarak tanımlanmalıdır.

AI dış çağrısı varsayılan olarak kapalıdır. Kontrollü pilotta aşağıdaki
değerlerin tamamı bilinçli olarak açılmalıdır:

```text
FIELD_AI_ENABLED=true
FIELD_AI_FORCE_OFF=false
FIELD_AI_DATA_PROCESSING_ALLOWED=true
FIELD_AI_API_KEY=<secret manager>
FIELD_AI_API_URL=<OpenAI-compatible endpoint>
FIELD_AI_MODEL=<vision-capable model>
```

Anahtar veya veri işleme izni yoksa analiz isteği başarısız durumunu açıkça
kaydeder; hiçbir varsayımsal bulgu üretilmez. Provider çıktısı `ai_draft`
durumunda kalır ve uzman kabul/reddetmeden denetim onaylanamaz.

Görsel analiz sistem promptu (`FIELD_AI_PROMPT_VERSION=field-visual-v2`)
Türkiye İSG görsel denetim disiplinini kullanır: geniş tarama, dar sonuç,
madde/ölçüm uydurmama, kanıt sınıfı kapısı ve kontrol hiyerarşisine dayalı
CAPA taslağı. Model çıktısı mevcut JSON sözleşmesine normalize edilir;
doğrulanmamış madde numarası saklanmaz.

## Fotoğraf ve GPS

Orijinal, analiz, işaretlenmiş ve önizleme nesneleri ayrı depolama anahtarları
olarak yazılır. GPS EXIF'ten okunmaz; denetim ve fotoğraf satırlarında enlem,
boylam, doğruluk, zaman, sağlayıcı ve alınamama nedeni ayrı alanlardır. Arka
planda konum takibi yapılmaz. İzin reddedilirse kullanıcı manuel açıklamayla
devam edebilir.

Her fotoğrafın tesis–alan–ekipman ve GPS bağlamı ayrıdır; denetim başlığı
yalnızca varsayılan değerleri taşır. Uzman işaretleri normalized koordinatlarla
ayrı tutulur ve yalnızca işaretlenmiş türevi günceller. Fotoğraf erişimi
korumalı API üzerinden yapılır; depolama anahtarları istemciye açılmaz.

## Mevzuat davranışı

AI yalnızca başlangıç mevzuat kataloğundaki başlıkları önerebilir. Madde/fıkra
numarası otomatik olarak doğrulanmış sayılmaz; uzman resmi kaynağı kontrol edip
ayrı uçtan doğrulamadıkça raporda `needs_expert_review` olarak görünür.

## Geri alma

AI pilotunu durdurmak için `FIELD_AI_FORCE_OFF=true` yapılabilir. Bu yalnızca
yeni AI analizini kapatır; kayıtlı fotoğraflar ve uzman taslakları silinmez.
Yeni bounded context'i geri almak için migration downgrade yalnızca bakım
planı ve yedekleme sonrası, açıkça onaylanmış operasyon olarak çalıştırılır.

## Saklama süresi

`FIELD_INSPECTION_RETENTION_DAYS=0` varsayılanında otomatik arşivleme kapalıdır.
Pozitif değer, uygulama başlangıcında kendiliğinden çalıştırılmaz; önce dry-run,
sonra açıkça planlanan bakım komutuyla kullanılır:

```bash
cd backend
python scripts/archive_expired_field_inspections.py
python scripts/archive_expired_field_inspections.py --execute
```

Bakım işi varsayılan olarak onaylı raporları korur, kayıtları silmez ve
orijinal fotoğraf nesnelerini temizlemez. Onaylı raporların da arşivlenmesi
ayrıca `--include-approved` ile açıkça seçilmelidir.
