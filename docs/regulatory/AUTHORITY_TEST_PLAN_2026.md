# İSG SUITE — Bakanlık Test Kabul Planı (İBYS + İSBS/e‑Reçete)

Bu plan yalnız Bakanlıkların güncel test dokümanı/test kodu teslim edildikten sonra uygulanır. Gerçek protokol alanları bu dokümanda bilinçli olarak tanımlanmamıştır.

## A. Ortak test kapıları

- Test/prod endpointleri source code'a gömülmez.
- Test/access code ve client secret yalnız secret store/env üzerinden verilir.
- Test ve production için ayrı enable switch kullanılır.
- Production switch varsayılan `false` kalır.
- Gönderim öncesi authenticated actor, tenant/OSGB/company kapsamı doğrulanır.
- Her payload canonical JSON hash'i ve idempotency key ile izlenir.
- Kişisel/sağlık payload'ı application loguna yazılmaz.
- Request/response correlation bilgisi, sonucu ve resmî hata kodu kişisel veriden ayrıştırılarak audit edilir.
- Timeout/5xx durumunda aynı idempotency key ile kontrollü retry yapılır.
- 4xx/iş kuralı reddinde otomatik sonsuz retry yapılmaz.
- Kabul edilen kayıt değiştirilecekse Bakanlığın versiyon/düzeltme yöntemi uygulanır; önceki kanıt kaybolmaz.

## B. İBYS kabul senaryoları

1. Resmî veri sözlüğü parser/schema testi.
2. Eksik zorunlu alan — local preflight reddi.
3. Geçersiz kod/değer — local preflight veya Bakanlık ret cevabı.
4. Yetkisiz OSGB/işyeri — tenant access reddi.
5. Yanlış profesyonel — görevlendirme/rol reddi.
6. Profesyonel e‑İmza/Mobil İmza senaryosu.
7. Kaynak payload hash'i ile imzalanan/iletilen veri bütünlüğü eşleşmesi.
8. Başarılı kabul + Bakanlık alındı/reference kaydı.
9. Duplicate gönderim — idempotency davranışı.
10. Bakanlık ret/hata kodu — kullanıcıya düzeltilebilir ve izlenebilir sonuç.
11. Timeout — kontrollü retry.
12. Daha önce gönderilmiş kaydın düzeltme/yenileme senaryosu, yalnız resmî yöntemle.

## C. İSBS/KTS veri aktarım testleri

KTS kılavuzuna göre Bakanlık test kodu ve test kılavuzu verildikten sonra veri aktarımı ve sağlık bilişimi standart uygunluk testleri uygulanır.

1. Bakanlığın verdiği sentetik test kişi/tesis verisi kullanılır.
2. Kimlik verisi Regulatory Identity Vault üzerinden adapter'a çözülür; log/UI'ye plaintext dönmez.
3. İşyeri hekimi rolü, görevlendirme ve tenant kapsamı doğrulanır.
4. Test kılavuzundaki tüm zorunlu veri alanları tek tek schema testine alınır.
5. Her Bakanlık hata kodu için kullanıcıya güvenli/düzeltilebilir mesaj eşlemesi yapılır.
6. Başarı cevabı application evidence store'a correlation/reference ile kaydedilir.

## D. E‑Reçete/RRS kabul senaryoları

1. Taslak reçete gönderilemez.
2. Yalnız `READY` reçete gönderime adaydır.
3. Reçeteyi yazan işyeri hekimi dışında gönderim yapılamaz.
4. Çalışan/işyeri/sağlık kaydı kapsam uyuşmazlığı reddedilir.
5. En az bir ilaç kalemi ve tanı bilgisi bulunur.
6. Tam kimlik yalnız vault'tan adapter'a verilir.
7. Resmî RRS profilindeki ilaç/tanı/kullanım alanları tam eşlenir.
8. Gönderim anında statü `SENDING`; sonuçta `APPROVED` veya `REJECTED` olur.
9. Bakanlık reçete/reference numarası başarı sonucunda saklanır.
10. Her attempt ayrı kaydedilir; son hata önceki deneme kanıtını silmez.
11. Aynı reçetenin yanlışlıkla çift oluşturulmasını/gönderilmesini idempotency önler.
12. İptal/düzeltme yalnız resmî protokol desteklediği biçimde yapılır.

## E. Çıkış kriteri

Production entegrasyonu ancak aşağıdaki beş şart birlikte sağlanınca açılır:

1. Kurumsal başvuru/tescil aşaması tamamlanmış.
2. Güncel resmî teknik profil sürümü arşivlenmiş.
3. Bakanlık testlerinin tamamı kabul edilmiş.
4. Yetkili kişi tarafından test kabul kanıtı release'e bağlanmış.
5. Production access code/registration no secret store'a girilmiş ve dört göz ile production switch açılmış.

Bu beş şarttan biri yoksa `authority_integration_gate` production gönderimini reddetmelidir.
