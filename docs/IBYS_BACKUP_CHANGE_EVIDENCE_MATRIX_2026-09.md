# ISGSuite İBYS Hazırlık — Veri Yedekleme ve Veritabanı Değişiklik Yönetimi Kanıt Matrisi

**Belge türü:** Teknik hazırlık / kanıt planı  
**Sistem:** ISGSuite OSGB  
**Kapsam:** ÇSGB İBYS Başvuru Formu #5 ve #6 ile ilişkili hazırlıklar  
**Tarih:** 30 Eylül 2026  
**Durum:** Canlı doğrulama ve altyapı eşleştirmesi devam ediyor

## 1. Kabul ilkesi

Bir gereklilik, kodda bulunması tek başına "tamamlandı" kabul edilmez.

**Gereklilik → Prosedür → Kod → Veritabanı → Konfigürasyon → Test → Canlı doğrulama → Kanıt → Kabul**

Bu zincirin üretim kanıtı bulunmayan halkaları açık olarak işaretlenir.

## 2. Mevcut teknik yapı

### Yedekleme kodu

Repo içinde mevcut:

- `backend/scripts/backup_database.py`
- `backend/scripts/backup_restore_drill.py`
- `backend/scripts/backup_key_rotation.py`
- `backend/scripts/workplace_backup_cron.py`
- `backend/app/services/backup_management.py`
- `backend/app/services/backup_restore.py`
- `backend/app/services/backup_safety.py`
- `backend/app/services/workplace_backup.py`
- `backend/app/services/archive_store.py`
- `docs/IBYS_YEDEKLEME_PROSEDURU.md`
- `backend/scripts/restore_database.md`

### Değişiklik/audit kodu

Repo içinde mevcut:

- `docs/IBYS_VERITABANI_DEGISIKLIK_PROSEDURU.md`
- `backend/app/services/audit.py`
- `backend/app/services/change_guard.py`
- `backend/app/services/change_request.py`
- `backend/scripts/audit_chain_verify.py`
- `backend/scripts/rebuild_audit_chain.py`
- `frontend/src/change_requests.jsx`
- `audit_logs`
- `change_requests`
- `change_request_events`
- PostgreSQL append-only/hash-chain migration'ları

## 3. Kritik canlı altyapı bulgusu — 30.09.2026

GitHub'daki `render.yaml` aşağıdaki cron servislerini tanımlıyor:

1. `isg-suite-db-backup-nightly`
2. `isg-suite-workplace-backups-nightly`
3. `isg-suite-backup-restore-drill-monthly`
4. `isg-suite-backup-integrity-weekly`
5. `isg-suite-audit-chain-verify-daily`

Ancak 30.09.2026 tarihinde Render workspace servis envanteri sorgulandığında canlıda ISGSuite repo için aşağıdakilerden yalnızca:

- `isg-suite-workplace-backups-nightly`
- `isg-suite-api-warmup-1u9t`
- `isg-suite-api-1u9t`
- `isg-suite-web-1u9t`

görüldü.

Bu nedenle **DB backup, restore drill, backup integrity ve audit-chain cron'ları canlıda aktif kabul edilmemelidir.**

Bu bir **P0/P1 altyapı uyum açığıdır** ve Bakanlık sunumundan önce kapatılıp gerçek çalışma kanıtları alınmalıdır.

### Canlıda doğrulanan olumlu bulgu

`isg-suite-workplace-backups-nightly` cron'u 28.09.2026 ve 29.09.2026 tarihlerinde başarıyla çalışmış; loglarda sırasıyla:

- `companies_seen=43`
- `created=43`
- `skipped=0`
- `failed=0`
- `purged=0`

sonuçları görülmüştür.

Bu yalnızca **işyeri backup cron'unun canlı çalıştığını** kanıtlar; tam PostgreSQL backup veya restore sisteminin canlı çalıştığını kanıtlamaz.

## 4. Kabul matrisi

| ID | Gereklilik | Teknik karşılık | Mevcut kanıt | Durum |
|---|---|---|---|---|
| B-05-01 | Tutulan verilerin yedeklenmesi | PostgreSQL backup cron | Render servisinde cron görünmüyor | 🔴 |
| B-05-02 | Ayrı ortam/off-site koruma | R2/S3 | Kod + config var, canlı backup kanıtı yok | 🟠 |
| B-05-03 | Yedek şifreleme | BACKUP_ENCRYPTION_KEY + Fernet | Kod/config var, canlı üretim kanıtı yok | 🟠 |
| B-05-04 | Yedek bütünlüğü | SHA-256 | Kod var, canlı integrity cron görünmüyor | 🔴 |
| B-05-05 | Saklama | GFS 30 gün/12 hafta/12 ay | render.yaml var, canlı cron yok | 🔴 |
| B-05-06 | Geri yükleme | Restore drill | Kod var, canlı cron görünmüyor | 🔴 |
| B-05-07 | Backup hata alarmı | Notification/audit | Kod var, canlı backup hata testi yok | 🟠 |
| B-05-08 | Tenant izolasyonu | workplace backup | Canlı cron başarıyla çalışıyor | 🟡 |
| B-05-09 | Değişiklik talebi | change_requests | Kod/UI mevcut | 🟡 |
| B-05-10 | Veri sahibi doğrulaması | identity verification | Kod/prosedür mevcut | 🟡 |
| B-05-11 | 4 göz prensibi | change_request service | Kod mevcut, canlı negatif QA bekliyor | 🟡 |
| B-05-12 | Old/new izlenebilirliği | audit_logs | Kod/migration mevcut | 🟡 |
| B-05-13 | Kör yazma engeli | conflict/409 | Kod/prosedür mevcut | 🟡 |
| B-05-14 | Hard-delete koruması | change_guard | Kod/test mevcut | 🟡 |
| B-05-15 | Silme öncesi arşiv | archive_records_before_delete | Kod mevcut | 🟡 |
| B-05-16 | Audit bütünlüğü | append-only + hash chain | Kod mevcut, canlı günlük cron görünmüyor | 🔴 |
| B-05-17 | Şema değişikliklerinin izlenebilirliği | Alembic | Repo migration yapısı mevcut | 🟡 |
| B-05-18 | Hassas veri log güvenliği | audit serialization | Teknik inceleme/test gerekli | 🟠 |
| B-05-19 | Production secret doğrulaması | Render secrets | Secret değerleri güvenlik nedeniyle içerik olarak okunmaz | 🟠 |
| B-05-20 | Kanıt paketi | QA/evidence bundle | Henüz tamamlanmadı | 🟠 |

## 5. Bakanlık öncesi zorunlu kapatma sırası

### P0 — Önce

1. Render'da PostgreSQL nightly backup cron'unu gerçek servis olarak oluştur/aktif et.
2. Backup cron'unun gerçek yedek üretmesini doğrula.
3. R2/S3 off-site kopyayı doğrula.
4. SHA-256 doğrulamasını canlı backup üzerinde kanıtla.
5. Şifreli backup üretimini kanıtla.

### P1 — Ardından

6. Restore drill cron'unu aktif et.
7. Gerçek yedek üzerinde dry-run restore PASS kanıtı üret.
8. Backup integrity cron'unu aktif et.
9. Audit-chain verify cron'unu aktif et.
10. Audit zincirinde canlı `chain_breaks=0`, `hash_breaks=0` kanıtı üret.

### P1 — Değişiklik yönetimi

11. Test veri kaydıyla değişiklik talebi oluştur.
12. 4 göz prensibinin tüm negatif senaryolarını çalıştır.
13. old/new değer ve gerekçe audit kaydını doğrula.
14. 409 conflict testini çalıştır.
15. hard-delete/dry-run/archive zincirini test et.
16. Sağlık verisinin gereksiz şekilde audit log'a yazılmadığını test et.

## 6. Kanıt dosyaları

Hedef kanıt seti:

- `backup-last-success.json`
- `backup-offsite-verification.json`
- `backup-integrity.json`
- `backup-restore-drill.json`
- `audit-chain-verify.json`
- `change-request-acceptance.json`
- `hard-delete-safety.json`
- `tenant-isolation-backup.json`
- `production-configuration-check.json`

Kanıt dosyalarında TCKN, sağlık tanısı, parola, API anahtarı veya gereksiz kişisel veri bulunmamalıdır.

## 7. Üretime alma kuralı

Bu branch üzerindeki hazırlıklar canlı sistemi doğrudan değiştirmez.

Üretime alınacak her değişiklik:

1. diff incelemesi,
2. test,
3. kontrollü deploy,
4. smoke/regresyon,
5. canlı doğrulama,
6. kanıt kaydı

adımlarından geçirilir.

**Temel ilke:** Mevcut çalışan ISGSuite fonksiyonları bozulmadan uyum hazırlığı yapılır.
