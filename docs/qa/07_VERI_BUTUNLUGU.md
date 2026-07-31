# 07 — Veri Bütünlüğü Değerlendirmesi

| Alan | Gözlem | Durum / risk |
| --- | --- | --- |
| Migration kurulumu | QA SQLite’da Alembic 0001→0012 başarıyla uygulandı | Geçti; 0013 bu koşuda uygulanmamış görünüyor |
| Firma silme / FK | Şirket silme ve bağlı kayıt davranışı çalıştırılmadı | Test edilemedi; yetim kayıt riski |
| Kullanıcı silme / FK | Sağlık çıktısı `users_delete: reassign-fk-refs` bilgisini içeriyor | Uçtan uca kanıt yok |
| Soft/hard delete | Modül bazında politika ve geri dönüş senaryosu doğrulanmadı | Test edilemedi |
| Yıllık plan idempotency | Aynı yıl ikinci generate çağrısı `created=0`, `skipped_existing=13` | Geçti |
| QA seed hijyeni | 3 firma, 17 kullanıcı, `TEST_`/`[TEST_DATA]` işaretleri | Kısmi geçti; temizleme akışı kanıtlanmadı |

## Değerlendirme

QA seed verisi canlı veriden ayrışacak biçimde adlandırılmıştır; test parolası yalnız QA içindir. Yine de test verisinin tekrar çalıştırıldığında temizlenmesi, yedeklere taşınmaması ve üretime hiç aktarılmaması bu turda kanıtlanmadı.

Firma silme, kullanıcı silme ve ilişkili belge/medya/sağlık/eğitim kayıtları için transaction, FK kuralı, audit kaydı ve dosya temizliği kontrollü QA senaryolarıyla test edilmelidir. Hard delete mi soft delete mi uygulanacağı her veri sınıfı için açıkça tanımlanmalıdır.
