# Faz 2 Kullanım Rehberi

## 1. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

## 2. Frontend
Yeni terminal açın:
```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Tarayıcı: `http://localhost:5173`

## Excel personel şablonu
Bir `.xlsx` dosyasının ilk satırına şu başlıkları yazın:
- Adı Soyadı
- T.C. Kimlik
- Branş/Görevi
- Departman
- İşe Giriş Tarihi
- Engelli/Hükümlü Durumu

## Faz 3 hedefi
- Risk değerlendirmesi
- Ramak kala
- İş kazası kayıtları
- DÖF yönetimi
- Risk puanı ve termin takibi
- Fotoğraf/dosya kanıtları
