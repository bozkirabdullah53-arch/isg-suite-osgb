# Eğitim Faz 3–6 Kabul Testi Kontrol Listesi

## A. Geriye uyumluluk

- [ ] Cutover öncesi legacy eğitim açılıyor.
- [ ] Cutover öncesi verified eğitimde mevcut sınav PDF'si yeniden indirilebiliyor.
- [ ] Cutover öncesi eğitimde mevcut sertifika PDF davranışı korunuyor.
- [ ] Tarihsel sınav snapshot sürümü ve content hash değişmiyor.

## B. Yeni NACE sınavı

- [ ] Cutover sonrası tam NACE ile yeni eğitim oluşturuluyor.
- [ ] `exam-selection-audit` strict enforced döndürüyor.
- [ ] Sınav toplam 20 soru içeriyor.
- [ ] İlk 5 soru sabit temel İSG soruları.
- [ ] Son 15 soru seçilen NACE snapshot'ındaki beş konuyla ilişkili.
- [ ] `genel_uretim` veya başka sektör alias sorusu bulunmuyor.
- [ ] Sınav policy değeri `exact-nace-snapshot-foundation-5-plus-work-specific-15-v2`.
- [ ] Aynı snapshot yeniden indirildiğinde soru metinleri değişmiyor.

## C. Katılım ve sonuç girişi

- [ ] Eğitim ekranında “Katılım ve Sonuçları Yönet” paneli görünüyor.
- [ ] Katılmayan kişiye puan girilemiyor.
- [ ] Katılan kişiye 0–100 arasında puan girilebiliyor.
- [ ] Toplu kayıt önceki final doğrulamasını kaldırıyor.
- [ ] Eksik puanla kesinleştirme reddediliyor.
- [ ] Başarı, puan ve geçme puanından otomatik hesaplanıyor.
- [ ] Başarısız kişi eğitim kaydında kalıyor fakat belgeye hak kazanamıyor.

## D. Belge üretimi

- [ ] Eğitim tamamlanmadan sertifika düğmesi kilitli.
- [ ] Katılım doğrulanmadan belge üretilemiyor.
- [ ] Sınav sonuçları doğrulanmadan belge üretilemiyor.
- [ ] En az bir başarılı katılımcı yoksa belge üretilemiyor.
- [ ] PDF yalnız başarılı ve katılmış kişileri içeriyor.
- [ ] PDF'deki belge numarası veritabanındaki certificate number ile aynı.
- [ ] Kamuya açık doğrulama yalnız hak kazanan kişileri gösteriyor.

## E. Teknik doğrulama

- [x] 2.141 NACE sınıflandırma testi
- [x] Her NACE için 15 benzersiz işe özgü soru testi
- [x] SQLite tam backend testi
- [x] PostgreSQL Alembic upgrade
- [x] PostgreSQL ORM–migration parity
- [x] PostgreSQL regresyonları
- [x] Frontend test
- [x] Frontend lint
- [x] Frontend build
- [x] Frontend E2E smoke
- [x] Frontend dependency audit
- [x] Cutover öncesi davranışı koruma testi
- [x] Feature-flag rollback testi

## F. Canlı gözlem

- [ ] Render API deploy `live`.
- [ ] Render web deploy `live`.
- [ ] `/health` 200.
- [ ] Startup loglarında iki training guard aktif.
- [ ] Deploy sonrasında yeni 5xx artışı yok.
- [ ] Rollback SHA ve bayrak kapatma komutu kayıtlı.
