# 16 — Tekrar Test Planı

**Başlatma koşulu:** Aşama 8 düzeltmeleri onaylanıp uygulanmış olmalıdır. Canlıya yazmadan önce izole QA ve PostgreSQL benzeri ortam kullanılır.

| Sıra | Alan | Tekrar test | Başarı ölçütü |
| ---: | --- | --- | --- |
| 1 | Konfigürasyon | Varsayılan `SECRET_KEY` ile prod mod başlatma; güçlü sırla login | Güvensiz başlatma engellenir |
| 2 | Rate limit | Login ve hassas endpointlerde sınır aşımı | 429, doğru reset ve kullanıcı dostu hata |
| 3 | Tenant | İki OSGB, üç firma, tüm rol/nesne kombinasyonları | Yetkisiz tüm istekler 403/404; izinli istekler başarılı |
| 4 | Sağlık | Uzman, CA, hekim, DSP, readonly; liste/tekil/export | Klinik/konfidansiyel alanlar yalnız yetkili rolde |
| 5 | Dosya | Traversal, MIME, boyut, malware simülasyonu, yetkisiz indirme | Reddedilir/karantinaya alınır; veri sızmaz |
| 6 | Eğitim verify | Geçerli/geçersiz kod ve yanıt PII incelemesi | Yalnız onaylı minimum veri döner |
| 7 | Migration | Boş ve veri içeren PostgreSQL 0001→0013; restore | Şema drift yok; yedekten geri dönüş başarılı |
| 8 | Fonksiyon | Test edilmemiş risk/olay/KKD/eğitim/CRM/finans/doküman/export | Her kritik CRUD ve hata akışı kanıtlı |
| 9 | UI/PDF/Excel | Tarayıcı E2E, responsive, indirme ve görsel kalite | Rol menüsü/API uyumu ve dosya içeriği kabul edilir |
| 10 | Deploy | Render cold/ılık başlangıç, ağ hatası, izleme | Hedef süre/hata eşiği sağlanır |

## Çıkış kriteri

P0 bulgular kapalı, P1 bulgular için tekrar test geçmiş, canlıya özgü migration/deploy kanıtı mevcut ve sonuçlar bu rapor setine eklenmiş olmalıdır. Başarısız senaryo yeniden açılan bulgu olarak kaydedilir; başarı oranı tahmin edilmez.
