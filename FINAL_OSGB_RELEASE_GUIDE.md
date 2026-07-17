# İSG Suite OSGB v0.9 — Yayın Adayı

Bu sürüm, OSGB'lerin çoklu müşteri işyeri, İSG profesyoneli, görevlendirme, saha ziyareti, CRM ve finans süreçlerini mevcut İSG modülleriyle birlikte yönetmesi için hazırlanmıştır.

## Yeni OSGB modülleri

- OSGB kuruluş yönetimi
- İSG profesyonelleri (uzman, hekim, DSP)
- Profesyonel–işyeri görevlendirmeleri
- Aylık zorunlu/planlanan/gerçekleşen süreler
- İSG-KATİP sözleşme numarası takibi
- Saha ziyaret takvimi ve tamamlama
- CRM ve satış fırsatları
- Gelir, gider, alacak ve cari takip
- OSGB operasyon ana paneli

## Güvenlik

- Kaynak kodda varsayılan admin e-postası ve şifresi bulunmaz.
- SECRET_KEY en az 32 karakter olmak zorundadır.
- İlk yönetici yalnızca SEED_ADMIN_EMAIL ve SEED_ADMIN_PASSWORD ortam değişkenleri tanımlanırsa oluşturulur.
- Gerçek `.env` dosyası GitHub'a yüklenmemelidir.

## Yerel çalıştırma

Backend:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Canlı yayın öncesi zorunlu ortam değişkenleri

- DATABASE_URL
- SECRET_KEY
- FRONTEND_ORIGIN
- SEED_ADMIN_EMAIL (ilk kurulumda geçici)
- SEED_ADMIN_PASSWORD (ilk kurulumda geçici)
- SMTP ayarları
- VITE_API_URL

İlk girişten sonra seed admin şifresini değiştirin ve seed değişkenlerini Render ortamından kaldırın.

## Doğrulanan işlemler

- Python compileall başarılı
- Temiz veritabanında Alembic 0001 → 0002 → 0003 başarılı
- Backend health endpoint 200
- Seed admin ile login 200
- Yetkili OSGB liste endpointi 200
- Frontend npm audit: 0 açık
- Vite production build başarılı

## Canlı yayın sınırı

Ödeme sağlayıcısı, İBYS, e-reçete, e-imza, SMS, S3/R2 dosya depolama ve antivirüs taraması dış servis kimlik bilgisi gerektirir. Altyapı canlıya alındıktan sonra bu servisler ayrıca bağlanmalıdır.
