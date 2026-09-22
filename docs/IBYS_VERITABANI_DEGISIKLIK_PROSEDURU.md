# İBYS Veritabanı Değişiklik Prosedürü

**Doküman sürümü:** 2.0
**Tarih:** 21 Eylül 2026
**Sahibi:** İSG Suite OSGB — Sistem Yöneticisi (bilgi işlem sorumlusu)
**İlgili standart:** ÇSGB İBYS Başvuru Formu #6 — "Uygulamayı kullanan kişi ve firmalardan
gelen veritabanında yapılması istenilen veri değişikliği taleplerinin ne şekilde
yönetileceği. (Değişiklik talepleri veri sahibinden yapılmalıdır.)"
**Son doğrulama:** 21 Eylül 2026 (kod ile birebir karşılaştırıldı)

---

## 0. Sürüm Geçmişi

| Sürüm | Tarih | Değişiklik |
|---|---|---|
| 1.0 | 26.08.2026 | İlk yayın |
| 2.0 | 21.09.2026 | **Değişiklik Talebi modülü** (talep → doğrulama → onay → uygulama) koda eklendi ve bu dokümanla hizalandı. 4 göz prensibi, KVKK md.11 veri sahibi başvuruları, kalıcı silme gerekçesi/dry-run/arşiv ve audit kapsamı belgelendi. |

## 1. Amaç ve Kapsam

Bu prosedür, İSG Suite OSGB uygulamasında tutulan verilerde müşteri/işveren/OSGB
tarafından talep edilen değişikliklerin nasıl alındığını, doğrulandığını,
uygulandığını ve denetlendiğini tanımlar.

**Temel ilke:** Veritabanında değişiklik yalnızca **veri sahibi** tarafından veya veri
sahibinin yazılı yetki verdiği kişi tarafından talep edilebilir. Üçüncü tarafların
(çalışan, başka OSGB) veri sahibi adına talebi, veri sahibi onayı olmadan kabul edilmez.

## 2. Roller

| Rol | Sorumluluk | Sistem karşılığı |
|---|---|---|
| Veri sahibi (işveren/OSGB yetkilisi) | Değişiklik talebinin kaynağı; kimliği doğrulanır | `change_requests.requester_type = employer \| data_subject` |
| Talep eden | Talebi açar (dilekçe) | `requested_by_user_id` |
| Doğrulayan | Kimliği ve talebi doğrular | `verified_by_id` (GLOBAL_ADMIN / COMPANY_ADMIN) |
| Onaylayan | Talebi onaylar | `approved_by_id` (yalnız GLOBAL_ADMIN) |
| Uygulayan | Onaylı değişikliği gerçek kayda uygular | `applied_by_id` (yalnız GLOBAL_ADMIN) |
| İSGGM (ÇSGB) | Mevzuat gereği değişiklik talebi/uygulama denetimi | Denetim çıktıları |

**4 göz prensibi (kodda zorunlu):**
1. Talebi açan kişi kendi talebini **onaylayamaz**.
2. Talebi doğrulayan kişi **onaylayamaz**.
3. Onaylayan kişi talebi **uygulayamaz**.

İhlalde API `403` döner (`app/services/change_request.py`).

## 3. Değişiklik Talebi Alma

1. **Kanal:** Talepler yalnızca kimliği doğrulanmış kanaldan alınır:
   - **Platform içi talep** (`POST /api/v1/change-requests`, giriş yapmış kullanıcı) —
     `channel=platform`
   - **Kurumsal e-posta** (kayıtlı yetkili kişinin adresinden) + imza/kaşe — `channel=email`
   - **Resmî yazı** (kaşe/imza) — `channel=official_letter`
2. **Kimlik doğrulama:** Talebi yapanın veri sahibi olduğu teyit edilir (kayıtlı yetkili
   eşleşmesi). KVKK başvurularında `POST /api/v1/change-requests/{id}/verify-identity`
   çağrılır ve `identity_verified=true` işaretlenir; bu adım tamamlanmadan veri paylaşılmaz.
3. **Kayıt:** Her talep benzersiz ve okunabilir numara ile kaydedilir: `CR-<yıl>-<sıra>`
   (örn. `CR-2026-0001`). Talep metni, tarih, talep eden ve doğrulama kanalı saklanır.
4. **Gerekçe zorunlu:** Her talepte en az 10 karakterlik gerekçe zorunludur; yoksa `422`.

## 4. İzin Verilen Değişiklik Tipleri

| Tip | Örnek | Yöntem | Sistem karşılığı |
|---|---|---|---|
| Düzeltme (veri sahibi hatası) | Çalışan adı/iletişim düzeltme | Platform arayüzü (rol bazlı) | `target_entity_type=employee` + beyaz liste alanı |
| Silme/hesap kapatma | Çalışan ayrılma, KVKK silme | Platform + onay akışı | `request_kind=erasure` (anonimleştirme) |
| Toplu veri taşıma | Excel içe aktarma | `employee_excel.py`, önizleme + onay | `POST /employees/import-excel` (audit'li) |
| Şema/altyapı değişikliği | Yeni alan, enum | Alembic migration (bkz. Bölüm 7) | `backend/alembic/versions/` |
| Tenant veri taşıma | OSGB'ye firma devri | Yalnız veri sahibi onayıyla | `request_kind=tenant_transfer` |

**Uygulanabilir alanlar (fail-closed beyaz liste):** `change_request_apply.FIELD_WHITELIST`

| Varlık | Talep yoluyla değiştirilebilen alanlar |
|---|---|
| `employee` | `full_name`, `job_title`, `department`, `special_status`, `start_date`, `exit_date`, `is_active` |
| `company` | `name`, `address`, `phone`, `authorized_person`, `nace_code`, `hazard_class` |
| `incident` | `sgk_report_date`, `sgk_reported`, `location`, `department`, `short_summary` |

Beyaz liste dışındaki alanlar (ör. `national_id_masked`) talep yoluyla **değiştirilemez**;
kimlik düzeltmeleri veri sahibi onayıyla ayrı yürütülür (Bölüm 10).

## 5. Değişiklik Uygulama Akışı

```
submitted ──verify──▶ verified ──approve──▶ approved ──apply──▶ applied
    │                    │                     │
    └──── reject ────────┴───── reject ────────┴──── reject
    └──── cancel ────────┴───── cancel ────────┴──── cancel
```

1. **Talep (`submitted`):** Veri sahibi/platform kullanıcısı talep açar. SLA: 10 gün
   (`sla_due_at`). Son tarihi geçen açık talepler `GET /change-requests/sla-overdue` ile izlenir.
2. **Doğrulama (`verified`):** Kimlik ve talep doğrulanır (GLOBAL_ADMIN/COMPANY_ADMIN).
3. **Onay (`approved`):** Yalnız GLOBAL_ADMIN onaylar; 4 göz kuralı uygulanır.
4. **Önizleme/Dry-run:** Toplu ve kalıcı işlemlerde önce önizleme zorunludur:
   - `POST /employees/bulk-delete` ve `POST /employees/bulk-purge` → `dry_run=true`
   - `DELETE /incidents/{id}` → `dry_run=true`
   Hiçbir kayıt değişmeden etkilenecek kayıtlar ve bağlı kayıtlar raporlanır.
5. **Uygulama (`applied`):** Onaylı talep gerçek kayda uygulanır. Uygulama sırasında:
   - Kaydın **mevcut değeri**, talepteki `old_value` ile karşılaştırılır. Arada başkası
     değiştirdiyse **409 çakışma** döner (kör yazma yapılmaz).
   - Değişiklik `audit_logs`'a eski/yeni değerle yazılır.
6. **Doğrulama:** Değişiklik sonrası veri bütünlüğü ve RLS kapsamı kontrol edilir.
7. **Bildirim:** Talep durum değişimleri `change_request_events` geçmişine yazılır ve
   denetim kaydına işlenir.

**Durum geçmişi:** Her geçiş `change_request_events` tablosuna (`from_status`,
`to_status`, `actor_user_id`, `note`, `created_at`) kaydedilir.

## 6. Kalıcı Silme (Hard Delete) Koruma Zinciri

Kalıcı silme geri alınamaz olduğundan aşağıdaki zincir zorunludur:

1. **Gerekçe zorunlu:** `reason` parametresi en az 10 karakter olmalıdır; yoksa `422`.
2. **Önizleme:** `dry_run=true` ile etkilenecek kayıtlar ve bağlı kayıtlar raporlanır.
3. **Silme öncesi arşiv:** Kayıtlar JSON olarak merkezi arşive yazılır
   (`app/services/change_guard.py::archive_records_before_delete`). Arşiv yazılamazsa
   silme **durdurulur** (fail-closed, `503`).
4. **Denetim kaydı:** İşlem `audit_logs`'a eski değer (silinen kayıt özeti) ve gerekçe
   ile yazılır (`employees_bulk_purged`, `incident_hard_deleted`).
5. **Bağlı kayıt koruması:** Sağlık, eğitim, KKD, acil ekip gibi bağlı kaydı olan
   personel kalıcı silinmez; neden listelenir.

**Firma (tenant) kalıcı silme:** `_purge_company_data` çalışmadan önce EYAS zinciri,
e-imza olayları ve sağlık revizyon/erişim logları JSON arşivine yazılır
(`audit_chain_archived_before_purge`); arşiv başarısızsa purge durdurulur.

## 7. Şema/Veritabanı Yapı Değişikliği (Alembic)

- **Tüm şema değişiklikleri versiyonlanmıştır:** `backend/alembic/versions/`.
  Manuel SQL değişikliği yasaktır.
- **Migration akışı:** Geliştirme → code review → CI'da `alembic upgrade head` +
  `scripts/ci_postgres_parity.py` → staging → production. Geri alınamayan
  (destructive) migration'larda önce yedek alınır.
- **Tek head kuralı:** CI `alembic heads` çıktısında tek head olduğunu doğrular
  (`test_migration_heads.py`, `Alembic single-head guard`).
- **Her migration'da `downgrade` zorunludur.**
- **RLS uyumu:** Her yeni tablo/alan migration'ı RLS policy ile gelir.
- **Regülatör veri ön kontrolü:** `regulatory_data_preflight.py` İBYS başvurusu
  öncesi veri kalitesini kontrol eder; eksik/yanlış veri tespit ederse engeller.

## 8. Reddedilen/Yetkisiz Talepler

- Veri sahibi olmayan kişinin talebi → reddedilir, gerekçe zorunlu (min 10 karakter)
  ve `change_request_rejected` olarak loglanır.
- Başka tenant'ın verisi için talep → reddedilir (`ensure_company_access`, RLS).
- Mevzuata aykırı (ör. geriye dönük sahte kayıt) → reddedilir, denetime bildirilir.
- Gizlilik Sözleşmesi 3.8 ve 3.14 gereği, yetkisiz kişilere veri değişikliği/aktarma
  yapılamaz.

## 9. Denetim ve İzleme

- Tüm değişiklikler `audit_logs` tablosunda (kullanıcı, IP, **tarayıcı/cihaz**,
  modül, aksiyon, zaman damgası, eski/yeni değer) saklanır. KVKK md.12 kapsamında
  izlenebilirlik sağlanır.
- **Tamper-evident zincir:** `audit_logs` append-only'dir (UPDATE/DELETE yasak) ve
  PostgreSQL'de SHA-256 hash zinciriyle korunur. Her kayıt bir öncekinin hash'ini taşır;
  değiştirilmiş kayıt zinciri kırar.
- **`user_agent` ve hash zinciri:** `user_agent` kolonu migration 0125 ile **additive**
  olarak eklenir ve deploy sırasında mevcut zincire dokunulmaz (kilit/timeout riski yok).
  Alanı hash zincirine dahil etmek isteyen operatör, bunu **bakım penceresinde** ayrı
  araçla yapar:
  ```
  python -m scripts.rebuild_audit_chain --dry-run   # rapor
  python -m scripts.rebuild_audit_chain --apply     # zinciri yeniden kur
  ```
  Araç yalnızca PostgreSQL'de çalışır, tek set-tabanlı ifadeyle (recursive CTE) zinciri
  kurar, sonunda zinciri yeniden doğrular ve hata hâlinde trigger'ları geri kurar.
- **Periyodik doğrulama:** `isg-suite-audit-chain-verify-daily` cron'u günlük olarak
  `python -m scripts.audit_chain_verify` çalıştırır. Zincir bozuksa exit 1 döner ve
  global yöneticilere kritik bildirim gönderilir. Sonuç `docs/qa/logs/audit-chain-verify.json`.
- **Firma kapsamı:** Denetim kaydı hedef kaydın firma id'siyle yazılır; OSGB yöneticisi
  başka firmanın kaydını değiştirdiğinde kayıt o firmanın denetim görünümünde kalır.
- OSGB yöneticisi kendi kapsamındaki değişiklik geçmişini görüntüleyebilir
  (`/api/v1/security/audit-logs`, rol bazlı).
- ÇSGB/İSGGM denetiminde değişiklik talebi kayıtları, onaylar ve audit log sunulur.

## 10. Özel Nitelikli Veriler

- **Sağlık verisi:** Yalnız yetkili hekim/DSP rolü değiştirebilir; `confidential_note`
  yalnız hekim erişimli (`health.py` rol kontrolü). Sağlık kayıtları sürüm bazlı ve
  hash zincirlidir (`health_record_revisions`); değişiklik gerekçesi zorunludur.
- **Kimlik (TCKN/YKN):** Şifreli vault'ta; tam değer uygulama katmanından döndürülmez
  (`regulatory_identity_vault.py`). Düzeltme yalnız veri sahibi onayıyla yürütülür ve
  talep beyaz listesi dışındadır.
- **ÇSGB'ye bildirim verisi:** İBYS/İSG-KATİP gönderiminde değişiklik/düzeltme,
  ilgili metot sözleşmesine göre yapılır (bkz. `ibys_client.py`, `katip_client.py`).

## 11. KVKK md.11 Veri Sahibi Başvuruları

| Başvuru türü | `request_kind` | Uygulama |
|---|---|---|
| Veri erişimi | `access` | `GET /change-requests/{id}/export` — kişinin verisi JSON |
| Düzeltme | `rectification` | Beyaz liste alanları, talep akışıyla |
| Silme | `erasure` | Kalıcı silme değil: soft delete + anonimleştirme |
| Taşınabilirlik | `portability` | `GET /change-requests/{id}/export` — makine okunur JSON |

- Başvuru `POST /api/v1/change-requests/data-subject` ile açılır.
- Kimlik doğrulanmadan (`identity_verified=false`) veri paylaşılmaz → `403`.
- Export çıktısında sağlık serbest metni **şifreli** (`enc:v1:`) döner; uç düz metin çözmez.
- Yasal saklama süresi olan kayıtlar (iş kazası, sağlık) silinmez; gerekçesiyle reddedilir.
- SLA: 10 gün; süre aşımı `sla-overdue` ucuyla izlenir.

## 12. Özellik Durumu (kod ile doğrulanmış)

| Özellik | Durum |
|---|---|
| Değişiklik talebi modülü (DB + API) | **Aktif** (`change_requests`, `change_request_events`) |
| Durum makinesi + geçiş geçmişi | **Aktif** |
| 4 göz prensibi (talep/doğrula/onayla/uygula) | **Aktif** (403 ile zorlanır) |
| Beyaz liste + çakışma kontrolü (409) | **Aktif** |
| Toplu işlemlerde dry-run önizleme | **Aktif** |
| Kalıcı silmede gerekçe + arşiv + denetim | **Aktif** |
| Purge öncesi denetim izi arşivleme | **Aktif** |
| audit_logs `user_agent` kolonu | **Aktif** (migration 0125; additive, zincire dokunmaz) |
| `user_agent`'ın hash zincirine dahil edilmesi | **Bakım aracı hazır** (`scripts.rebuild_audit_chain`; bakım penceresinde çalıştırılır) |
| Günlük zincir doğrulama + alarm | **Aktif** (`isg-suite-audit-chain-verify-daily`) |
| KVKK md.11 erişim/taşınabilirlik export'u | **Aktif** |
| Erasure'da otomatik anonimleştirme | **Kısmi** (talep + onay + yasal kontrol; anonimleştirme mevcut `user_retirement` servisiyle yürütülür) |
| Otomatik CRUD audit katmanı (before_flush) | **Planlanan** |
| audit_logs partition/arşiv politikası | **Planlanan** |

## 13. Referanslar

- Kod: `backend/app/api/change_requests.py`, `backend/app/services/change_request.py`,
  `backend/app/services/change_request_apply.py`, `backend/app/services/change_guard.py`,
  `backend/app/services/audit.py`, `backend/app/services/audit_chain.py`
- Migration: `backend/alembic/versions/0125_audit_user_agent.py`,
  `backend/alembic/versions/0127_change_requests.py`
- Scriptler: `backend/scripts/audit_chain_verify.py`
- Arayüz: `frontend/src/change_requests.jsx`, `frontend/src/change_requests_logic.js`
- RLS: `backend/app/core/rls.py`, `backend/app/core/tenant_context.py`
- Gizlilik Sözleşmesi: md.3.8 (veri aktarım yasağı), md.3.12 (veri sahipliği),
  md.3.14 (ticarete konu edilemez), Başvuru Formu #6
