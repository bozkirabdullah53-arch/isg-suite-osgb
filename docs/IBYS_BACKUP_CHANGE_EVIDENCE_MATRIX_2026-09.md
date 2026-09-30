# ISGSuite İBYS Hazırlık — Veri Yedekleme ve Veritabanı Değişiklik Yönetimi Kanıt Matrisi

**Belge türü:** Teknik hazırlık / kanıt planı  
**Sistem:** ISGSuite OSGB  
**Kapsam:** ÇSGB İBYS Başvuru Formu #5 ve #6 ile ilişkili hazırlıklar  
**Tarih:** 30 Eylül 2026  
**Durum:** Canlı doğrulama öncesi kontrollü hazırlık

## 1. Amaç

Bu belge, veri yedekleme ve veritabanı değişiklik yönetimi gerekliliklerinin yalnızca doküman seviyesinde değil; uygulama kodu, veritabanı, altyapı yapılandırması, testler ve üretim kanıtları ile doğrulanmasını sağlamak amacıyla hazırlanmıştır.

**Kabul ilkesi:** Bir gereklilik, kodda bulunması tek başına "tamamlandı" kabul edilmez. Üretim için aşağıdaki zincirin kurulması gerekir:

Gereklilik → Prosedür → Kod → Veritabanı → Konfigürasyon → Test → Canlı doğrulama → Kanıt → Kabul.

## 2. Mevcut teknik envanter

### 2.1 Yedekleme

Mevcut repoda aşağıdaki bileşenler bulunmaktadır:

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

Tanımlı mekanizmalar:

- günlük tam PostgreSQL yedeği
- GFS günlük/haftalık/aylık saklama
- Fernet tabanlı şifreli arşiv
- R2/S3 off-site kopya
- boyut + SHA-256 doğrulaması
- backup retention
- restore dry-run
- aylık restore drill
- haftalık backup bütünlük taraması
- kritik hata bildirimi
- backup audit olayları
- RPO yaş kontrolü

### 2.2 Veritabanı değişiklik yönetimi

Mevcut repoda aşağıdaki bileşenler bulunmaktadır:

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

Tanımlı mekanizmalar:

- veri değişiklik talebi
- kimlik doğrulama
- doğrulama/onay/uygulama ayrımı
- dört göz prensibi
- alan beyaz listesi
- old/new value kaydı
- optimistic/concurrency kontrolü
- dry-run
- hard-delete gerekçesi
- silme öncesi arşiv
- audit trail
- append-only audit log
- hash chain
- günlük hash-chain doğrulaması

## 3. Resmi kabul matrisi

| ID | Gereklilik | Teknik karşılık | Kanıt | Kabul kriteri | Durum |
|---|---|---|---|---|---|
| B-05-01 | Tutulan verilerin yedeklenmesi | PostgreSQL backup cron | Render cron + backup log | Başarılı günlük backup | 🟡 |
| B-05-02 | Yedeklerin ayrı ortamda korunması | R2/S3 off-site | R2 object + checksum | Off-site kopya doğrulanmış | 🟡 |
| B-05-03 | Yedek şifreleme | BACKUP_ENCRYPTION_KEY + Fernet | Config + test | Şifreli backup üretimi | 🟡 |
| B-05-04 | Yedek bütünlüğü | SHA-256 | Backup integrity çıktısı | checksum eşleşiyor | 🟡 |
| B-05-05 | Saklama politikası | GFS retention | Render config + test | 30 gün/12 hafta/12 ay | 🟡 |
| B-05-06 | Geri yükleme | restore drill | QA JSON | Gerçek backup dry-run PASS | 🟡 |
| B-05-07 | Backup başarısızlık alarmı | Notification/audit | Alarm + log | Kritik alarm üretiliyor | 🟡 |
| B-05-08 | Tenant yedek izolasyonu | workplace backup | Tenant testleri | Başka firmanın verisi dahil değil | 🟡 |
| B-05-09 | Değişiklik talebi | change_requests | UI/API + DB | Talep kayıtlı | 🟡 |
| B-05-10 | Veri sahibi doğrulaması | identity verification | Change request kaydı | Doğrulama olmadan uygulama yok | 🟡 |
| B-05-11 | 4 göz prensibi | change_request service | Negatif QA testleri | Kendi talebini onaylama mümkün değil | 🟡 |
| B-05-12 | Old/new değer izlenebilirliği | audit_logs | Audit kaydı | Eski/yeni değer mevcut | 🟡 |
| B-05-13 | Kör yazmanın önlenmesi | conflict/409 kontrolü | QA testi | Eski değer değişmişse uygulama durur | 🟡 |
| B-05-14 | Hard-delete koruması | change_guard | QA | Gerekçesiz silme engellenir | 🟡 |
| B-05-15 | Silme öncesi arşiv | archive_records_before_delete | Archive + audit | Arşiv başarısızsa silme durur | 🟡 |
| B-05-16 | Audit bütünlüğü | append-only + hash chain | audit verification | chain/hash break = 0 | 🟡 |
| B-05-17 | Şema değişikliklerinin izlenebilirliği | Alembic | migration history | Manuel SQL değişikliği yok | 🟡 |
| B-05-18 | Hassas veri log güvenliği | audit serialization | KVKK/security test | Gereksiz sağlık verisi loglanmıyor | 🟠 |
| B-05-19 | Üretim secret doğrulaması | Render secrets | Secret presence check | Anahtarlar mevcut ve güçlü | 🟡 |
| B-05-20 | Canlı kanıt dosyası | QA/evidence bundle | tarihli JSON/log | Her kritik test kanıtlanmış | 🟠 |

**Not:** 🟡 = kod/config mevcut, üretim kanıtı ayrıca doğrulanmalı. 🟠 = ayrıca teknik kabul testi yapılmalı. Bu tablo canlı sistemde test yapılmadan "tamamlandı" olarak işaretlenmemelidir.

## 4. Zorunlu üretim kabul testleri

### Yedekleme

1. Son başarılı günlük backup zamanını doğrula.
2. Backup dosyasının şifreli olduğunu doğrula.
3. SHA-256 değerini doğrula.
4. R2/S3 off-site nesnesini doğrula.
5. Yerel/off-site checksum eşleşmesini doğrula.
6. Tenant yedeğinde yalnız hedef firmanın verisinin bulunduğunu doğrula.
7. Gerçek yedekten izole restore dry-run çalıştır.
8. Kritik tablo ve kayıt sayılarında tutarlılık kontrolü yap.
9. Başarısız backup senaryosunda kritik alarm üretimini test et.
10. Test sonucunu tarih, sürüm, backup kimliği ve checksum ile kaydet.

### Veritabanı değişikliği

1. Bir test kaydında değişiklik talebi oluştur.
2. Talep eden kişinin kendi talebini onaylayamadığını doğrula.
3. Doğrulayan kişinin onaylayamadığını doğrula.
4. Onaylayan kişinin uygulayamadığını doğrula.
5. Old/new değerlerin audit'e işlendiğini doğrula.
6. Aynı kayıt arada değiştirilirse 409 conflict üretildiğini doğrula.
7. Gerekçesiz hard-delete işlemini reddettir.
8. Dry-run sonucunda canlı verinin değişmediğini doğrula.
9. Silme öncesi arşivin oluştuğunu doğrula.
10. Audit hash zincirini doğrula.
11. Audit zincirini kasıtlı olarak bozulan test ortamında doğrulama alarmını test et.
12. Sağlık verisi gibi özel nitelikli verilerin gereksiz içerikle audit log'a yazılmadığını doğrula.

## 5. Canlı doğrulama için gerekli kanıt paketi

Bakanlık sunumu için teknik kanıtların aşağıdaki şekilde tarihli ve sürümlü tutulması hedeflenir:

- `backup-last-success.json`
- `backup-offsite-verification.json`
- `backup-integrity.json`
- `backup-restore-drill.json`
- `audit-chain-verify.json`
- `change-request-acceptance.json`
- `hard-delete-safety.json`
- `tenant-isolation-backup.json`
- `production-configuration-check.json`
- test çalıştırma tarihi/saatı
- uygulama commit SHA
- test ortamı
- test sonucu
- sorumlu
- varsa hata ve düzeltme kaydı

Kanıt dosyalarında TCKN, sağlık tanısı, parola, API anahtarı veya başka gereksiz hassas veri tutulmamalıdır.

## 6. Kritik açıklar / karar noktaları

### 6.1 Off-site zorunluluk

Repo yapılandırmasında `BACKUP_REMOTE_REQUIRED=false` kontrollü rollout amacıyla bırakılmıştır. Bakanlık sunumundan önce R2/S3 off-site yedekleme gerçek ortamda doğrulanmalı ve kabul kriterleri sağlandıktan sonra zorunlu moda geçiş ayrıca değerlendirilmelidir.

### 6.2 Restore

`BACKUP_RESTORE_ENABLED=false` üretimde güvenli varsayılan olarak bırakılmıştır. Gerçek restore yazımı yalnızca kontrollü bakım penceresinde ve onaylı süreçle yapılmalıdır. Normal kabul testi dry-run ile yapılmalıdır.

### 6.3 WORM/değiştirilemez arşiv

Mevcut prosedürde WORM/değiştirilemez arşiv gelecekteki geliştirme olarak belirtilmiştir. Bu, başvuru maddesinin açık bir şartı olarak doğrulanmadan zorunlu kabul edilmemeli; ancak yüksek güvence seçeneği olarak ayrıca değerlendirilmelidir.

### 6.4 DR failover

Otomatik DR failover mevcut kodda tamamlanmış kabul edilmemelidir. Mevcut sistemin RTO/RPO hedefleri ile fiili altyapı kapasitesi ayrıca doğrulanmalıdır.

## 7. Değişiklik yönetimi kuralı

Bu hazırlık branch'i üzerinde yapılan çalışmalar canlı sistemi doğrudan değiştirmez.

Üretime alınacak her değişiklik:

1. kod değişikliği,
2. test,
3. diff incelemesi,
4. kabul,
5. kontrollü deploy,
6. smoke/regresyon,
7. kanıt kaydı

adımlarından geçirilmelidir.

**Temel ilke:** Mevcut çalışan ISGSuite fonksiyonları bozulmadan uyum hazırlığı yapılır.
