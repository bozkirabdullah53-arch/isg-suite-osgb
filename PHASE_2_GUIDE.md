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
Örnek şablonu Personel Yönetimi → "Örnek Excel'i İndir" ile alabilirsiniz
(tek sayfa: `PERSONEL LİSTESİ`). Başlıklar ilk satırda şu sırayla yer alır:
- # (satır no, zorunlu değil)
- Adı Soyadı (zorunlu)
- TC Kimlik No
- Görevi
- Engelli/Hükümlü
- Giriş Tarihi (GG.AA.YYYY)
- Çıkış Tarihi (GG.AA.YYYY)

Eski başlıklar (T.C. Kimlik, Branş/Görevi, Departman, İşe Giriş Tarihi,
İşten Çıkış Tarihi, Engelli/Hükümlü Durumu) ve `EYLÜL 2026 PERSONEL LİSTESİ`
gibi aylık sayfa adları da tanınır. Boş hücreler mevcut kayıtlardaki
bilgileri silmez; yalnızca dolu gönderilen alanlar güncellenir.

## Faz 3 hedefi
- Risk değerlendirmesi
- Ramak kala
- İş kazası kayıtları
- DÖF yönetimi
- Risk puanı ve termin takibi
- Fotoğraf/dosya kanıtları
