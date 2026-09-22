# İBYS Yedekleme Prosedürü

**Doküman sürümü:** 2.2
**Tarih:** 22 Eylül 2026
**Sahibi:** İSG Suite OSGB — Sistem Yöneticisi (bilgi işlem sorumlusu)
**İlgili standart:** ÇSGB İBYS Başvuru Formu #5 — "Tutulan veriler için yedekleme prosedürü"
**Son doğrulama:** 22 Eylül 2026 (kod ve `render.yaml` ile birebir karşılaştırıldı)

---

## 0. Sürüm Geçmişi

| Sürüm | Tarih | Değişiklik |
|---|---|---|
| 1.0 | 26.08.2026 | İlk yayın |
| 2.0 | 21.09.2026 | Kod-ile-hizalama: gerçek cron adları/saatleri, offsite (R2) kopya, GFS saklama, gerçek yedekle tatbikat, alarm ve denetim kayıtları. Uygulanmayan maddeler "planlanan" olarak işaretlendi. |
| 2.1 | 22.09.2026 | Offsite yedek zorunlu hâle getirildi (fail-closed başlatma). |
| 2.2 | 22.09.2026 | **Güvenli kademeli rollout:** fail-closed başlatma Aşama 2'ye alındı; Aşama 1'de offsite açık + doğrulanmış + alarmlı, ancak canlıyı düşürmeyen mod. Offsite hatası artık kritik bildirim üretir. |

## 1. Amaç ve Kapsam

Bu prosedür, İSG Suite OSGB uygulamasında tutulan verilerin yedeklenmesi, şifrelenmesi,
saklanması, geri yüklenmesi ve yedek bütünlüğünün test edilmesi süreçlerini tanımlar.

**Kapsam:** Üretim veritabanı (PostgreSQL), yükleme depolamadaki dosyalar (dokümanlar,
sağlık kaydı ekleri, arşiv paketleri) ve şifreli tenant (işyeri) yedekleri.

## 2. Sorumluluklar

| Rol | Sorumluluk |
|---|---|
| Sistem yöneticisi | Yedekleme cron'larının çalışmasının izlenmesi, başarısızlık müdahalesi, anahtar saklama |
| OSGB yöneticisi | Kendi OSGB kapsamındaki yedek/geri yükleme taleplerinin onayı |
| Veri sahibi (işveren/OSGB) | Veri değişiklik/geri yükleme talebinin kurum onaylı olarak iletilmesi |
| İSGGM (ÇSGB) | Denetim ve gerektiğinde yedek/geri yükleme talebi |

## 3. Yedek Sıkılığı ve Saklama (GFS)

| Veri tipi | Sıklık | Saklama | Uygulama |
|---|---|---|---|
| Veritabanı (tam) | **Günlük 22:00 UTC = 01:00 TR** | Günlük 30 gün | `isg-suite-db-backup-nightly` → `python -m scripts.backup_database` |
| Veritabanı (haftalık katman) | Otomatik (GFS) | 12 hafta | Her ISO haftasının en yeni yedeği |
| Veritabanı (aylık katman) | Otomatik (GFS) | 12 ay | Her ayın en yeni yedeği |
| İşyeri yedek paketi | **Günlük 23:00 UTC = 02:00 TR** | 30 gün (otomatik) | `isg-suite-workplace-backups-nightly` → `scripts.workplace_backup_cron` |
| İşyeri manuel yedeği | Talep ile | Otomatik silinmez | `/api/v1/workplace-backups` |
| Tenant yedeği (v3) | Talep/abonelik ile | Abonelik + 30 gün | Fernet şifreli ZIP |

**Yapılandırma:** `DB_BACKUP_RETENTION_DAYS=30`, `DB_BACKUP_WEEKLY_RETENTION_WEEKS=12`,
`DB_BACKUP_MONTHLY_RETENTION_MONTHS=12`, `WORKPLACE_BACKUP_RETENTION_DAYS=30`.

**Saklama ilkesi:** Saklama süresi dolan yedekler GFS katmanlarına göre otomatik silinir
(KVKK md.7/f.1 — veri saklama süresi). Her otomatik silme işlemi `workplace_backup_purged`
denetim kaydı olarak `audit_logs`'a yazılır. Yasal saklama yükümlülüğü (6331 ve alt
düzenlemeler) gereği daha uzun süreli tutulması gereken kayıtlar ayrı yasal arşive taşınır.

## 4. Şifreleme ve Anahtar Yönetimi

- **Yedekler Fernet (AES-128-CBC + HMAC-SHA256)** ile şifrelenir (`backup_restore.py`).
- **Production'da şifreleme zorunludur (fail-closed).** Anahtar yoksa veya zayıfsa
  (`backup_encryption_key_status()` → `missing`/`weak`) günlük yedek **üretilmez**;
  script hata kodu ile biter. Bu davranış `scripts/backup_database.py::_resolve_encryption`
  içinde uygulanır.
- **Şifreleme anahtarı:** `BACKUP_ENCRYPTION_KEY` (en az 32 karakter, rastgele).
  Kaynak koda yazılmaz; yalnızca Render Dashboard / secret manager'da tutulur.
- **Anahtar saklama ve kurtarma:** Anahtarın en az iki kopyası ayrı fiziksel konumda
  (kurumsal parola kasası + mühürlü zarf) saklanır. Anahtar kaybolursa şifreli yedekler
  açılamaz; bu nedenle anahtar yedeği yedekten ayrı tutulur.
- **Anahtar rotasyonu:** `python -m scripts.backup_key_rotation --rotate --old-key … --new-key …`
  Tüm şifreli yedekleri yeni anahtarla yeniden şifreler, her dosyayı doğrular; hata
  durumunda hiçbir dosyayı kalıcı değiştirmez. `--dry-run` ile önizleme yapılır.
- **Sağlık alanları:** `HEALTH_FIELD_ENCRYPTION_KEY` ile ayrı şifrelenir
  (`health_field_crypto`). Yedekte şifreli halde korunur.
- **Kimlik vault'u:** `REGULATORY_IDENTITY_ENCRYPTION_KEY` ile tam TCKN/YKN şifreli;
  yedekte anahtar olmadan açılamaz.

## 5. Yedek Alma Akışı

1. **Otomatik tam veritabanı yedeği (günlük 01:00 TR):** `isg-suite-db-backup-nightly`
   cron'u `python -m scripts.backup_database` çalıştırır.
   - PostgreSQL: `pg_dump --format=custom --no-owner --no-acl` (parola argv'ye değil
     `PGPASSWORD` ortam değişkenine verilir).
   - SQLite (yalnız geliştirme): dosya kopyası.
   - Şifreleme → **offsite (R2/S3) kopya** → boyut + SHA-256 doğrulaması.
   - GFS saklama uygulanır; sonuç tek satır JSON olarak stdout'a basılır.
2. **İşyeri (tenant) yedeği (günlük 02:00 TR):** `isg-suite-workplace-backups-nightly`
   cron'u imzalı çağrıyla `POST /api/v1/workplace-backups/internal/run-scheduled`
   tetikler. Yedek API servisinin kalıcı diskinde (`/var/data/backups`) üretilir.
3. **Tenant bazlı (talep):** OSGB yöneticisi `POST /api/v1/archives/backup` ile kendi
   kapsamı için şifreli ZIP paketi üretir. Ham hassas veri yerine SHA-256 özeti tutulur.
4. **Production fail-closed:** `BACKUP_RESTORE_ENABLED=false` iken geri yükleme
   kapalıdır; sessiz/yanlış geri yükleme yapılamaz.

## 6. 3-2-1 Kuralı ve Offsite Kopya

- **Yerel kopya:** `/var/data/backups` (Render kalıcı disk).
- **Offsite kopya:** Cloudflare R2 / S3 (`BACKUP_REMOTE_ENABLED=true`,
  `BACKUP_REMOTE_PREFIX=db-backups`). Yükleme sonrası nesnenin **boyutu ve SHA-256
  özeti** uzaktan okunarak doğrulanır; doğrulama başarısızsa uzak nesne silinir ve
  yerel yedek korunur (`backup_management.upload_backup_to_offsite`).
- **Kademeli (güvenli) rollout:**
  - **Aşama 1 — aktif:** `BACKUP_REMOTE_ENABLED=true`, `BACKUP_REMOTE_REQUIRED=false`.
    Yedek R2/S3'e yüklenir ve **boyut + SHA-256** ile doğrulanır. Kimlik bilgisi
    eksik/erişilemezse uygulama **yine de açılır** (canlı düşmez); ancak offsite
    doğrulama başarısız olursa global yöneticilere **kritik alarm** gönderilir ve
    cron `exit 1` döner. Yani hata sessiz kalmaz.
  - **Aşama 2 — offsite çalıştığı doğrulandıktan sonra:** `BACKUP_REMOTE_REQUIRED=true`
    yapılır. O andan itibaren kimlik bilgisi eksikse production **başlamaz**
    (fail-closed, `config._validate_backup_offsite_credentials`) ve offsite
    doğrulanmayan yedek başarısız sayılır.
  - **Doğrulama ölçütü (Aşama 2 öncesi):** günlük cron JSON çıktısında en az 3 gün
    üst üste `"offsite": {"uploaded": true}` görülmesi.

## 7. Geri Yükleme Akışı

1. **Talep:** Veri sahibi (işveren/OSGB) yazılı onaylı geri yükleme talebi.
2. **Onay:** Sistem yöneticisi + OSGB yöneticisi onayı. `BACKUP_RESTORE_ENABLED=true`
   yalnızca işlem süresince açılır.
3. **Dry-run:** Önce `python -m scripts.backup_restore_drill --latest` ile **gerçek
   yedek** üzerinde dry-run doğrulaması yapılır (diske yazmaz).
4. **Geri yükleme:** `restore_database.md` prosedürü uygulanır; şifre çözme →
   staging doğrulama → production uygulama.
5. **Doğrulama:** Veri bütünlüğü, RLS kapsamları ve şifreli alanların açılabilirliği
   kontrol edilir.
6. **Kapatma:** `BACKUP_RESTORE_ENABLED=false` ile kapatılır; işlem `audit_logs`'a yazılır.

## 8. Yedek Testi (Geri Yükleme Tatbikatı)

- **Sıklık:** Ayda 1 (her ayın 15'i 21:00 UTC) ve büyük sürüm öncesi.
- **Yöntem:** `isg-suite-backup-restore-drill-monthly` cron'u
  `python -m scripts.backup_restore_drill --out docs/qa/logs/backup-restore-drill.json --latest`
  çalıştırır. **Gerçek yedek** seçilir (sentetik dosya üretilmez):
  - ZIP/şifreli ZIP: checksum → `inspect_backup_file` ile manifest → dry-run geri yükleme
    → manifest dosya sayısı ile dry-run sonucu karşılaştırılır.
  - DB dump: boyut + SHA-256 + (varsa) şifre çözülebilirlik.
- **Kanıt:** `docs/qa/logs/backup-restore-drill.json` (dosya, checksum, `ran_at`, PASS/FAIL).
- **Başarısızlık:** Script exit code 1 döner; sistem yöneticisi uyarılır, kök neden
  giderilmeden bir sonraki günlük yedek devreye alınmaz.

## 9. Bütünlük Taraması

- **Sıklık:** Haftalık (Pazar 20:00 UTC) — `isg-suite-backup-integrity-weekly`.
- **Yöntem:** `python -m scripts.backup_key_rotation --out docs/qa/logs/backup-integrity.json`
  (`--rotate` verilmezse tarama modu) tüm yedekleri listeler ve SHA-256/boyut doğrular.
- **Alarm:** Bozuk yedek bulunursa global yöneticilere kritik bildirim gönderilir ve
  script exit code 1 döner.

## 10. Felaket Kurtarma (DR)

- **RTO (kurtarma süresi):** 4 saat
- **RPO (kabul edilebilir veri kaybı):** 24 saat (günlük yedek)
- **RPO izleme:** `/health` ve release status çıktısı, son başarılı yedeğin yaşı
  `BACKUP_MAX_AGE_HOURS` (varsayılan 36 saat) sınırını aşarsa `degraded` döner.
- **DR ortamı:** Yedek bölge/ortam, birincil erişilemez hale gelirse devreye girer.
  Gizlilik Sözleşmesi 3.20 gereği DR merkezi de aynı güvenlik şartlarına tabidir.

## 11. İzleme ve Denetim

- Yedek başarı/başarısızlık sonucu her cron çalışmasında JSON olarak loglanır.
- **Başarısız otomatik yedekte** global yöneticilere `Notification` (kritik) gönderilir;
  hata detayı firma bazında `logger.exception` ile kaydedilir.
- **Yedek denetim izi:** İşyeri yedeği oluşturma, indirme, içerik inceleme ve saklama
  süresi sonunda silme işlemleri `audit_logs`'a yazılır
  (`workplace_backup_created|downloaded|inspected|purged`).
- ÇSGB/İSGGM denetiminde yedek listesi, saklama süreleri ve test raporları sunulur.

## 12. Yedekleme Özellik Durumu (kod ile doğrulanmış)

| Özellik | Durum |
|---|---|
| Günlük tam DB yedeği cron | **Aktif** (`isg-suite-db-backup-nightly`) |
| İşyeri yedeği cron | **Aktif** (`isg-suite-workplace-backups-nightly`) |
| Aylık gerçek tatbikat cron | **Aktif** (`isg-suite-backup-restore-drill-monthly`) |
| Haftalık bütünlük taraması | **Aktif** (`isg-suite-backup-integrity-weekly`) |
| Offsite (R2/S3) kopya + boyut/checksum doğrulama | **Aktif** (`BACKUP_REMOTE_ENABLED=true`) |
| Offsite hatasında kritik alarm | **Aktif** (sessiz kalmaz, canlıyı düşürmez) |
| Offsite zorunlu (fail-closed başlatma) | **Aşama 2'ye hazır** (`BACKUP_REMOTE_REQUIRED=false`; doğrulama sonrası `true`) |
| Production'da şifreleme zorunluluğu | **Aktif** (fail-closed) |
| Yedek olaylarının denetim kaydı | **Aktif** |
| RPO yaş izleme / degraded sağlık | **Aktif** |
| Anahtar rotasyon aracı | **Aktif** (`scripts/backup_key_rotation.py`) |
| Otomatik DR failover | **Planlanan** (henüz kodda yok) |
| WORM / değiştirilemez arşiv | **Planlanan** |

## 13. Referanslar

- Kod: `backend/app/services/backup_restore.py`, `backend/app/services/backup_management.py`,
  `backend/app/services/backup_safety.py`, `backend/app/services/workplace_backup.py`,
  `backend/app/services/archive_store.py`
- Scriptler: `backend/scripts/backup_database.py`, `backend/scripts/backup_restore_drill.py`,
  `backend/scripts/backup_key_rotation.py`, `backend/scripts/workplace_backup_cron.py`
- Cron tanımları: `render.yaml`
- Geri yükleme: `backend/scripts/restore_database.md`
- KVKK veri envanteri: `docs/security/kvkk-data-inventory.md`
- Üretim kontrol listesi: `PRODUCTION_CHECKLIST.md`
- Gizlilik Sözleşmesi md.3.16 (veri güvenliği), 3.20 (felaket merkezi)
