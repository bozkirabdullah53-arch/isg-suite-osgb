# Eğitim Modülü Manuel Smoke Senaryosu

## Senaryo 1 — Eski kayıt korunuyor

1. Cutover öncesinde oluşturulmuş bir eğitimi açın.
2. Daha önce oluşturulan sınav PDF'sini indirin.
3. Katılım belgesi PDF'sini indirin.
4. Eski içerik ve indirme işlevlerinin değişmediğini doğrulayın.

## Senaryo 2 — Yeni verified eğitim

1. Cutover sonrasında tam NACE seçerek yeni temel İSG eğitimi oluşturun.
2. Eğitim tarih aralığını tehlike sınıfına uygun belirleyin.
3. Katılımcıları ekleyin.
4. “Sınav Oluştur” ile 20 soruluk PDF alın.
5. İlk 5 sorunun temel, kalan 15 sorunun snapshot konularına bağlı olduğunu kontrol edin.

## Senaryo 3 — Sonuç ve belge

1. “Katılım ve Sonuçları Yönet” panelini açın.
2. Bir katılımcıyı başarılı, birini başarısız, birini devamsız girin.
3. Sonuçları kaydedin.
4. Kesinleştirmeyi çalıştırın.
5. Başarılı katılımcı sayısının 1 olduğunu doğrulayın.
6. Sertifika PDF'sinde yalnız başarılı katılımcının bulunduğunu kontrol edin.
7. Kamuya açık doğrulama kodunda yalnız hak kazanan kişinin göründüğünü kontrol edin.

## Senaryo 4 — Güvenli blokaj

1. Yeni eğitimde puan girmeden kesinleştirme deneyin.
2. İşlemin açıklayıcı 422 hatasıyla reddedildiğini doğrulayın.
3. Eğitim tamamlanmadan sertifika indirmeyi deneyin.
4. Sertifika düğmesinin kilitli ve backend'in belge üretimini reddettiğini doğrulayın.

## Senaryo 5 — Rollback

1. İki strict bayrağı `false` yapın.
2. Servisin sağlıklı başladığını doğrulayın.
3. Mevcut legacy sınav ve belge akışının yeniden kullanıldığını doğrulayın.
