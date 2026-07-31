# Faz 7 — Ticari Sürüm Hazırlığı

Bu paket Faz 1–7'nin tamamını içerir ve sürüm adı **İSG Suite v1.0 Final Adayı**dır.

## Eklenenler

- Alembic migration altyapısı
- İlk veritabanı baseline migration dosyası
- Backend başlangıcında migration çalıştıran start script
- SQLite ve PostgreSQL yedekleme komutu
- Geri yükleme rehberi
- SMTP e-posta servis altyapısı
- PWA manifesti
- Service worker ve temel çevrimdışı önbellek
- Mobil ana ekrana eklenebilir uygulama yapısı
- Üretim kontrol listesi
- Render başlangıç komutu güncellemesi
- v1.0 son paket yapısı

## Yerel çalıştırma

Backend:

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Veritabanı migration

Yeni migration oluşturma:

```bash
alembic revision --autogenerate -m "degisiklik aciklamasi"
```

Migration uygulama:

```bash
alembic upgrade head
```

Geri alma:

```bash
alembic downgrade -1
```

## Son durum

Kod tabanı ticari ürün geliştirmesine uygun bir temel sağlar; ancak gerçek müşteri
verisiyle yayına alınmadan önce `PRODUCTION_CHECKLIST.md` içindeki güvenlik ve
operasyon maddeleri tamamlanmalıdır.
