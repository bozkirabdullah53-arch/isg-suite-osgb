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

## Güvenlik sertleştirmesi

- JWT altyapısı `PyJWT==2.10.1` ve sınırlı algoritma listesiyle çalışır; `python-jose` kaldırılmıştır.
- Docker imajları UID 1000 ile çalışan `appuser` kullanır.
- Docker Compose PostgreSQL kullanıcı adı, veritabanı, parola ve `DATABASE_URL` değerlerini zorunlu ortam değişkeni olarak ister; kaynak kodunda varsayılan parola yoktur.
- Render üretim Blueprint'inde sağlık alanı şifrelemesi ve kontrollü dosya geri yükleme etkinleştirilmiştir. `HEALTH_FIELD_ENCRYPTION_KEY` ve `BACKUP_ENCRYPTION_KEY` değerleri Render Dashboard'da gizli olarak tanımlanmalıdır.
- Production ortamı SQLite'ı, HTTP frontend origin'lerini ve geçersiz CORS origin'lerini reddeder.
- Ayrıntılı sistem sağlık ve iş durumu endpoint'leri kimlik doğrulamalıdır; herkese açık `/health` yalnızca liveness bilgisi verir.
- Access token kalıcı `localStorage` içinde tutulmaz; sekme oturumu bellekte/`sessionStorage` içinde, yenileme belirteci HttpOnly cookie içindedir.
- İBYS/İSG-KATİP adapter'ları resmi API sözleşmesi ve erişim bilgileri sağlanana kadar kontrollü stub/dry-run durumundadır; sahte canlı entegrasyon eklenmemiştir.

## Yetkili Firma Yönetimi

OSGB yöneticileri için tenant-kapsamlı **Yetkili Firma Yönetimi** modülü eklenmiştir.

- Firma kartı: OSGB/işyeri bağlantısı, unvan, konum, temsilci, iletişim, çalışan sayısı, tehlike sınıfı, yetki kapsamı/numarası ve düzenlenme–başlangıç–bitiş–inceleme tarihleri.
- Belge ve profesyonel uygunluğu: eksik, süresi dolmuş, 30/60/90 gün içinde dolacak belge uyarıları; profesyonel belge/geçerlilik/görevlendirme/sözleşme/hizmet süresi kontrolleri.
- Şeffaf skor: 10 uygunluk ve 8 kalite kategorisi; puan, ağırlık, başarısız kontrol, kritik engel, önerilen aksiyon ve skor geçmişi görünürdür. Kara kutu puanlama kullanılmaz.
- Ticari ve denetim araçları: çoklu filtreler, OSGB durum özeti, tek tık firma PDF/Excel dosyası, durum Excel'i, bildirimler, otomatik eksik listesi ve ZIP denetim hazırlık paketi.
- Gelişmiş akışlar: 11 adımlı onboarding, otomatik görev/belge kontrol listesi, OSGB-içi firma kalite sıralaması, yalnız global yöneticiye açık anonim OSGB karşılaştırma API'si ve Denetim Günü görünümü.
- Gizlilik: sağlık bilgisi yalnız anonim toplamlar olarak kullanılır; kişi veya klinik ayrıntı firma kartı, skor, bildirim ya da çıktılarda yer almaz.
- Kapsam sınırı: yeni modül yalnız kurum içi kayıt ve hazırlık yönetimidir; harici gönderim, resmî doğrulama veya kabul işlemi yapmaz.

Veritabanı geçişi: `0104_authorized_firm_compliance`. Uygulama ve güvenlik ayrıntıları için `AUTHORIZED_FIRM_UPGRADE_REPORT.md` belgesine bakın.

## Docker Compose ile yerel çalıştırma

`docker compose` çalıştırmadan önce `.env` dosyanızda aşağıdaki değişkenleri güçlü, yerel değerlerle tanımlayın:

```dotenv
POSTGRES_DB=isgsuite
POSTGRES_USER=isgsuite
POSTGRES_PASSWORD=<güçlü-postgres-parolası>
DATABASE_URL=postgresql+psycopg://<kullanıcı>:<parola>@db:5432/<veritabanı>
SECRET_KEY=<en-az-32-karakter-rastgele-anahtar>
```

Ardından yapılandırmayı doğrulayın ve servisleri başlatın:

```bash
docker compose config
docker compose up --build
```

`POSTGRES_*`, `DATABASE_URL` veya `SECRET_KEY` eksikse Compose'un başlamayı reddetmesi beklenen güvenlik davranışıdır.
