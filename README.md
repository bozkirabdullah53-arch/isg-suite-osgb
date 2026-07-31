# İSG Suite v1.0 Final Adayı

# İSG Suite — Faz 2 Birleşik Proje

Bu paket Faz 1'in tüm altyapısını ve Faz 2 yönetim modüllerini birlikte içerir.

## Faz 2 ile gelenler
- Firma ekleme, listeleme, arama ve pasife alma API'leri
- Şube ekleme, listeleme, güncelleme ve pasife alma API'leri
- Kullanıcı oluşturma, rol atama, güncelleme ve pasife alma API'leri
- Personel ekleme, arama, güncelleme ve pasife alma API'leri
- `.xlsx` dosyasından toplu personel aktarımı
- Firma bazlı veri izolasyonu
- Global yönetici ve firma yöneticisi yetki sınırları
- Gerçek çalışan React yönetim ekranları
- Mobil uyumlu açık mavi-yeşil tema

## Demo giriş
- İlk yönetici bilgileri yalnızca `.env` içindeki `SEED_ADMIN_EMAIL` ve `SEED_ADMIN_PASSWORD` ile oluşturulur.

## Çalıştırma
Backend ve frontend kurulumları Faz 1 ile aynıdır. Ayrıntılar için `PHASE_2_GUIDE.md` dosyasını okuyun.

> Eski Faz 1 klasörü yerine bu Faz 2 paketini kullanın. Bu paket Faz 1 + Faz 2'nin birleşik sürümüdür.


## Faz 3
Risk, ramak kala, iş kazası, DÖF ve eğitim modülleri eklenmiştir.


## Faz 4
Sağlık kayıtları, doküman yönetimi, yıllık planlar ve temel KPI raporları eklenmiştir.


## Faz 5
Güvenli dosya yükleme/indirme, Excel-PDF dışa aktarım, parola değiştirme ve denetim kayıtları eklenmiştir.


## Faz 6
Abonelik, demo süresi, bildirim merkezi, sistem sağlık kontrolü ve temel rate limiting eklenmiştir.


## Faz 7
Alembic migration, yedekleme, SMTP altyapısı, PWA ve üretim kontrol listesi eklenmiştir.

## OSGB v0.9 güncellemesi

Proje artık OSGB üst kuruluşu, müşteri işyerleri, uzman/hekim/DSP, görevlendirme, saha takvimi, CRM ve finans işlevlerini içerir. Yayın ve ortam değişkenleri için `FINAL_OSGB_RELEASE_GUIDE.md` belgesine bakın.
