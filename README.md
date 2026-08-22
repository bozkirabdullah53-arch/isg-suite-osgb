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
