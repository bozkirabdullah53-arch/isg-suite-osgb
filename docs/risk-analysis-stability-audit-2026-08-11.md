# Risk Analizi stabilite denetimi — 11.08.2026

## Bulgular ve uygulanan düzeltmeler

### Öncelikli risk → detay yönlendirmesi

Öncelikli risk kartları doğru `risk.id` değerini kullanıyordu; ancak detay isteği
tamamlanana kadar önceki detay ekranda kalabiliyor, hızlı ardışık tıklamalarda da
daha eski ağ yanıtı son seçimin üzerine yazabiliyordu. Bu durum kullanıcıda
“yanlış kayda/yanlış yere gitti” algısı oluşturuyordu.

Uygulanan güvenlikler:

- Her detay isteği bir sıra numarasıyla izleniyor; yalnızca son istek ekranı güncelleyebiliyor.
- Sunucu yanıtındaki `id`, istenen kayıt ID’siyle doğrulanıyor.
- Detay rotası istek başında seçilen kayıtla eşleştiriliyor.
- Ağ hatasında bozuk detay rotası risk listesine çevriliyor ve kullanıcıya görünür hata veriliyor.
- Detay açıldığında ekran ilgili detay bölümüne odaklanıyor.

### Yöntem bağlamı

Üstteki aktif çalışma yöntemi yeni kayıt/çalışma alanını, kayıt detayındaki
yöntem ise o riskin oluşturulurken kullanılan yöntemini temsil eder. Bu iki
bağlam birbirine sessizce yazılmıyordu; detayda yöntem bağlamı açık bir bilgi
alanı olarak görünür hale getirildi. Böylece Fine–Kinney kaydı incelenirken üst
çalışma alanının 5×5 görünmesi açıklanabilir ve mevcut yöntem/kayıt verisi
değiştirilmez.

### Korunan akışlar

- 5×5 Matris ve Fine–Kinney hesaplama akışları değiştirilmedi.
- Risk oluşturma, düzenleme, silme, DÖF, medya ve rapor uç noktaları değiştirilmedi.
- Mevcut risk geçmişi/geri dönüş URL yapısı korunarak yalnızca detay yükleme
  yarışları güvenli hale getirildi.
- Backend erişim kontrolü ve seçili yöntemli rapor filtresi bu düzeltmede
  değiştirilmedi.

## Doğrulama

- `npx vite build` başarılı.
- Risk detay kimliği ve mevcut navigasyon testleri başarılı.
- `git diff --check` temiz.
- Backend yerel ortamında `pytest` kurulu olmadığı için backend testleri CI
  üzerinde doğrulanmalıdır.

## Canlı smoke test senaryosu

1. Risk Analizi merkezinde iki öncelikli kayda art arda tıklanır; yalnızca son
   tıklanan risk detayının kodu, faaliyeti ve yöntemi görünmelidir.
2. Detay açıkken tarayıcı Geri ve “Listeye dön” denenir; risk listesine dönülmelidir.
3. Fine–Kinney ve 5×5 kayıtları ayrı ayrı açılır; O/F/Ş alanları yalnızca
   ilgili yöntemde görünmelidir.
4. Raporlar sekmesinde yöntem seçilip Excel/PDF/DÖF çıktısı alınır; seçilmeyen
   yöntemin kayıtları çıktıya karışmamalıdır.
