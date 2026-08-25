# İBYS Yedekleme Prosedürü

**Doküman sürümü:** 1.0
**Tarih:** 26 Ağustos 2026
**Sahibi:** [Firma adı doldurulacak]
**İlgili standart:** ÇSGB İBYS Başvuru Formu #5 — "Tutulan veriler için yedekleme prosedürü"

---

## 1. Amaç ve Kapsam

Bu prosedür, İSG Suite OSGB uygulamasında tutulan verilerin yedeklenmesi, şifrelenmesi,
saklanması, geri yüklenmesi ve yedek bütünlüğünün test edilmesi süreçlerini tanımlar.

**Kapsam:** Tüm üretim veritabanı (PostgreSQL), yükleme depolamadaki dosyalar
(dokümanlar, sağlık kaydı ekleri, arşiv paketleri) ve şifreli tenant yedekleri.

## 2. Sorumluluklar

| Rol | Sorumluluk |
|---|---|
| Sistem yöneticisi | Yedekleme zamanlamasının çalıştığının izlenmesi, başarısızlık müdahalesi |
| OSGB yöneticisi | Kendi OSGB kapsamındaki yedek/geri yükleme taleplerinin onayı |
| Veri sahibi (işveren/OSGB) | Veri değişiklik/geri yükleme talebinin kurum onaylı olarak iletilmesi |
| İSGGM (ÇSGB) | Denetim ve gerektiğinde yedek/geri yükleme talebi |

## 3. Yedek Sıklığı ve Saklama

| Veri tipi | Sıklık | Saklama süresi | Not |
|---|---|---|---|
| Veritabanı (tam) | Günlük (gece 03:00) | 30 gün | `pg_dump` ile |
| Veritabanı (haftalık) | Pazar | 12 hafta | Aylık saklamaya dönüşür |
| Veritabanı (aylık) | Ayın 1'i | 12 ay | Uzun süreli arşiv |
| Dosya depolama | Günlük artımlı | 30 gün | S3/R2 bucket versiyonlama |
| Tenant yedek paketi | Talep/abonelik ile | Abonelik + 30 gün | Fernet şifreli ZIP |

**Saklama ilkesi:** Saklama süresi dolan yedekler otomatik silinir (KVKK md.7/f.1
— veri saklama süresi). Yasal saklama yükümlülüğü (6331 ve alt düzenlemeler) gereği
daha uzun süreli tutulması gereken kayıtlar ayrı yasal arşive taşınır.

## 4. Şifreleme

- **Tüm yedekler şifrelidir.** Yedek paketleri Fernet (AES-128-CBC + HMAC-SHA256) ile
  şifrelenir (`backup_restore.py`).
- **Şifreleme anahtarı:** `BACKUP_ENCRYPTION_KEY` ortam değişkeni (en az 32 karakter,
  üretimde güçlü rastgele anahtar). Anahtar kaynak koda yazılmaz, yalnızca güvenli
  sırlar yöneticisinde (Render Dashboard / secret manager) tutulur.
- **Sağlık alanları:** `HEALTH_FIELD_ENCRYPTION_KEY` ile ayrı şifrelenir
  (`health_field_crypto`). Yedekte şifreli halde korunur.
- **Kimlik vault'u:** `REGULATORY_IDENTITY_ENCRYPTION_KEY` ile tam TCKN/YKN şifreli;
  yedekte anahtar olmadan açılamaz.

## 5. Yedek Alma Akışı

1. **Otomatik (günlük):** Render Cron job `scripts/backup_database.py` çalıştırır.
   - `pg_dump` → şifreli paket → nesne depolama (S3/R2) yüklenir.
   - Başarı/başarısızlık metrik olarak loglanır.
2. **Tenant bazlı (talep):** OSGB yöneticisi `POST /api/v1/osgb/.../backup` ile kendi
   OSGB kapsamı için şifreli ZIP paketi talep eder. Paket `BACKUP_ENCRYPTION_KEY`
   ile şifreli, ham hassas veri yazılmaz (yalnız SHA-256 özeti).
3. **Production fail-closed:** `BACKUP_RESTORE_ENABLED=false` iken geri yükleme
   kapalıdır; sessiz/yanlış geri yükleme yapılamaz.

## 6. Geri Yükleme Akışı

1. **Talep:** Veri sahibi (işveren/OSGB) yazılı onaylı geri yükleme talebi.
2. **Onay:** Sistem yöneticisi + OSGB yöneticisi onayı. `BACKUP_RESTORE_ENABLED=true`
   olarak açılır (yalnızca işlem süresince).
3. **Dry-run:** Önce `backup_restore_drill.py` ile staging'te dry-run testi.
4. **Geri yükleme:** `restore_database.md` prosedürü uygulanır; şifre çözme →
   staging doğrulama → production uygulama.
5. **Doğrulama:** Veri bütünlüğü, RLS kapsamları ve şifreli alanların açılabilirliği
   kontrol edilir.
6. **Kapatma:** `BACKUP_RESTORE_ENABLED=false` ile kapatılır; işlem audit log'a yazılır.

## 7. Yedek Testi (Geri Yükleme Tatbikatı)

- **Sıklık:** Ayda 1 (her ayın 15'i) ve büyük sürüm öncesi.
- **Yöntem:** `backup_restore_drill.py` — rastgele yedek seçilir, staging ortamında
  açılır, veri tutarlılığı doğrulanır, sonuç `docs/qa/logs/backup-restore-drill.json`
  olarak kaydedilir.
- **Başarısızlık:** Test başarısız olursa sistem yöneticisi uyarılır, kök neden
  giderilmeden bir sonraki günlük yedek devreye alınmaz.

## 8. Felaket Kurtarma (DR)

- **RTO (kurtarma süresi):** 4 saat
- **RPO (kabul edilebilir veri kaybı):** 24 saat (günlük yedek)
- **DR ortamı:** Yedek bölge/ortam, birincil erişilemez hale gelirse devreye girer.
  Gizlilik Sözleşmesi 3.20 gereği DR merkezi de aynı güvenlik şartlarına tabidir.

## 9. İzleme ve Denetim

- Yedekleme başarı/başarısızlık metrikleri izleme panelinde (uptime/log servisi).
- Başarısız yedek alarmı sistem yöneticisine anlık iletilir.
- ÇSGB/İSGGM denetiminde yedek listesi, saklama süreleri ve test raporları sunulur.

## 10. Referanslar

- Kod: `backend/app/services/backup_restore.py`, `backend/scripts/backup_database.py`,
  `backend/scripts/backup_restore_drill.py`, `backend/app/services/backup_safety.py`
- Geri yükleme: `backend/scripts/restore_database.md`
- KVKK veri envanteri: `docs/security/kvkk-data-inventory.md`
- Üretim kontrol listesi: `PRODUCTION_CHECKLIST.md`
- Gizlilik Sözleşmesi md.3.16 (veri güvenliği), 3.20 (felaket merkezi)
