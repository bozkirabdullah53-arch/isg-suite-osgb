# Faz 1 Mimari Kararları

## Seçilen yapı

- Backend: Python 3.11 + FastAPI
- ORM: SQLAlchemy 2
- Veritabanı: PostgreSQL; yerel hızlı başlangıç için SQLite
- Frontend: React + Vite
- Kimlik doğrulama: JWT Bearer
- Dağıtım: Render ve Docker
- Tasarım: açık tema, mavi-yeşil kurumsal renk sistemi

## Güvenlik sınırları

- Global yönetici tüm firmaları görebilir.
- Diğer roller yalnızca kendi firma verilerine erişebilir.
- Sağlık verileri için sonraki fazda ayrı tablo ve daha sıkı rol kontrolleri kurulmalıdır.
- TC kimlik numarası başlangıç modelinde maskeli tutulur.
- Üretimde SECRET_KEY çevresel değişken olarak saklanmalıdır.
- Varsayılan yönetici şifresi ilk girişte değiştirilmelidir.

## Sonraki geliştirme sırası

1. Alembic migration
2. Kullanıcı ve rol yönetim ekranı
3. Firma/şube CRUD
4. Personel tekli ve Excel toplu aktarım
5. Audit log
6. Risk değerlendirme
7. Ramak kala ve iş kazası
8. Eğitim
9. Sağlık modülü
10. PDF/Excel raporlama
