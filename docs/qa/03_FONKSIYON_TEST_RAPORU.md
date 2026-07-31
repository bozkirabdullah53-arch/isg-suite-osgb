# 03 — Fonksiyon Test Raporu

**Tarih:** 2026-07-20  
**Ortam:** İzole SQLite QA; canlı ortam ve canlı DB kullanılmadı.  
**Kanıt:** `02B_SMOKE_SONUCLARI.md`, `03A_FONKSIYON_SMOKE.md`, `logs/qa-api-smoke.json`.

Sonuçlar yalnızca gerçekleştirilen API smoke ve mevcut otomatik test kapsamını ifade eder. “Test edilemedi” sonucu, işlevin çalışmadığı anlamına değil, bu turda doğrulanmadığı anlamına gelir.

| Modül | Test | Sonuç | HTTP/not | Risk |
| --- | --- | --- | --- | --- |
| Auth | GA login, hatalı parola, `/auth/me` | Geçti | 200 / 401 / 200 | Düşük; JWT derin testi ayrı |
| Firma | GA firma listesi; tokensız erişim | Geçti | 200, 3 `TEST_` firma; 401 | Orta |
| Personel | Diğer firmaya personel erişimi | Geçti | 403; görevlendirme kapsamı mesajı | Orta; tek IDOR örneği |
| Görevlendirme | GA liste | Geçti | 200, n=9 | Orta; durum değiştirme test edilmedi |
| Risk | CRUD, medya, PDF | Test edilemedi | Bu turda çağrı yok | Orta |
| Olay | CRUD, DÖF ve PDF | Test edilemedi | Bu turda çağrı yok | Orta |
| KKD | Zimmet CRUD ve export | Test edilemedi | Bu turda çağrı yok | Orta |
| Eğitim | Geçersiz public verify | Geçti | 200, `valid:false` tasarımı | Orta-Yüksek; PII testi yok |
| Sağlık | Uzman erişimi; hekim liste | Kısmi geçti | Uzman 403; hekim 200 | Yüksek; alan/CA gizliliği eksik |
| Yıllık Plan | Uzman generate, tekrar generate | Geçti | 200; ilk çalışmada 13 kayıt, tekrar idempotent | Düşük |
| CRM | Liste/oluşturma/değiştirme | Test edilemedi | Bu turda çağrı yok | Orta |
| Finans | Liste/oluşturma/değiştirme | Test edilemedi | Bu turda çağrı yok | Orta |
| Bildirim | Liste, üretme, okunmuş durumu | Test edilemedi | Bu turda çağrı yok | Orta |
| ÇSGB | Paket, kanıt ve öncelik ekranları | Test edilemedi | Bu turda çağrı yok | Orta |
| Doküman | Meta CRUD ve binary dosya | Test edilemedi | Bu turda çağrı yok | Yüksek; upload ayrı raporda |
| Rapor/Export | PDF/Excel içerik ve indirme | Test edilemedi | Endpoint varlığı envanterden biliniyor | Orta |

## Ek kanıt

- `pytest`: 11/11 geçti; ancak testler HTTP uçtan uca, dosya, IDOR ve sağlık gizliliğini kapsamıyor.
- Frontend üretim derlemesi başarıyla tamamlandı; bu, tarayıcı iş akışlarının doğrulandığı anlamına gelmez.
- Otomatik yıllık plan üretimi izole QA’da başarılıdır. Canlıdaki geçmiş “Failed to fetch” durumu bu testle iş kuralı hatası olarak doğrulanmamıştır.

## Hüküm

Fonksiyonel temel smoke olumlu, ancak modül matrisi kapsamı kısmi kalmıştır. Test edilmemiş modüller için kabul kararı verilmemelidir. Düzeltme uygulanmadı.
