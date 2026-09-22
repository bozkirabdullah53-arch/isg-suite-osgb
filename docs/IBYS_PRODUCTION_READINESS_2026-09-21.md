# İBYS Üretim Hazırlık veGap Raporu — 2026-09-21

Kapsam: ÇSGB İBYS kayıt/veri seti gereksinimleri, e-imza (5070), kurumsal altyapı,
yedekleme/audit ve güvenlik sertleştirme alanlarının **kod tabanında doğrulanmış**
durumu. İlke: mock veri ve uydurma endpoint YOK — resmî sözleşme gelene kadar
entegrasyon bilinçli fail-closed (`authority_integration_gate`, REVIEW_FIX_REPORT.md).

---

## 1) Kurumsal ve İdarî Altyapı

| Gereksinim | Durum | Kanıt |
|---|---|---|
| Resmî bildirim/mailler @isgsuite.tr | ✅ Mevcut | `render.yaml` SMTP_USERNAME/FROM=info@isgsuite.tr |
| E-posta传输 şifreleme (In-Transit) | ⛔ **Sağlayıcı engeli** — isimtescil hiçbir TLS portu vermiyor (2026-09-21 probe: 587 STARTTLS yok, 465/993/995 kapalı, POP3 STLS yok) | Güvenlik raporu F-01; çözüm paketi: `docs/SECURITY_INFRA_ROLLOUT.md` §1 (Brevo cutover, hazırlanmış) |
| İSG-KATİP 48 saat penceresi hazırlığı | ✅ Otomasyon hazır (aşağıdaki runbook) | `osgb.py` katip-prep/export/readiness; `sync-field-roles`; gate |

### KATİP 48 Saatlik Pencere Runbook (yetkilendirme geldiği anda)
1. **Ön hazırlık (şimdi yapılabilir):**
   - `GET /api/v1/osgb/integration-readiness` — secret varlığı presence-only raporlanır (değer sızmaz).
   - `GET /api/v1/osgb/katip-prep` + `/katip-prep/export.csv` — görevlendirme veri setini dışa aktar, eksikleri tamamla.
   - `POST /api/v1/osgb/sync-field-roles` ve `/capacity/sync-all-required` — saha rolleri/kapasite senkronu.
2. **Yetki penceresi açılınca (dakikalar içinde):**
   - Render env: `KATIP_API_URL` + `KATIP_API_KEY` (secret) gir.
   - `POST /api/v1/osgb/integrations/katip/dry-run` → `probe` → `live-send`.
   - `assert_authority_send_allowed()` gate'i secret yoksa gönderimi **reddeder** (fail-closed); canonical SHA-256 + idempotency kanıtı üretilir (`docs/regulatory/TECHNICAL_EVIDENCE_MAP_2026.md`).
3. **Doğrulama:** `security/audit-logs` + `test_regulatory_application_readiness` (CI).
> Resmî İBYS/KATİP REST sözleşmesi ve test kodları repo'da YOK; adapter bilinçli
> stub/dry-run'dadır. Sözleşme gelmeden canlı gönderim denemek reddedilir — bu bir
> eksik değil, tasarım kararıdır (sahte entegrasyon yasağı).

---

## 2) Veritabanı, Loglama ve Süreç Yönetimi

### Yedekleme / Disaster Recovery
- Şifreli tenant yedekleri: `workplace_backup.py` + `backup_safety.py` (SHA-256 checksum, `hmac.compare_digest`), retention 30 gün, cron 02:00 TR (`render.yaml` cron servisi + imzalı `WORKPLACE_BACKUP_CRON_TOKEN`).
- Geri yükleme: inspect/plan her zaman; gerçek yazma `BACKUP_RESTORE_ENABLED` + `confirm=RESTORE` — **F-04 ile production'da kapatıldı**, dry-run bozulmadı.
- Nesne depolama: local→R2/S3 dual-mirror + `object_storage_remote_required` fail-closed; video backfill idempotent job.
- Testler: `test_workplace_backups.py`, `test_tenant_backup_v3.py`.

###Immutable Audit Trail (bu revizyonda tamamlandı)
- **0121** (ekip): `audit_logs` PostgreSQL trigger ile append-only + `prev_hash/event_hash` SHA-256 zinciri + backfill.
- **0122 (YENİ — P0):** 0121'in katı guard'ı, kullanıcı/firma **kalıcı silme akışlarındaki FK-detach UPDATE'lerini** de engelleyip production'da silme uçlarını 500'e düşürecekti (`users._detach_user_refs`, `companies._purge_company_data`; SQLite testleri bunu yakalayamaz). 0122:
  - Guard'ı daralttı: DELETE her zaman yasak; UPDATE yalnız `user_id/company_id → NULL` (tüm hash'li içerik kolonları değişmezse) — başka her değişiklik yine RAISE.
  - Canonical hash yeniden tanımlandı (mutable FK kolonları kimlik dışında) + zincir rebuild → doğrulama detach sonrası da tutarlı.
  - `audit_chain_verify()` SQL fonksiyonu: set-tabanlı `chain_breaks` + `hash_breaks` sayacı.
  - **Atıf koruması:** detach'ten önce append-only atıf olayı yazılır (`audit_actor_detach`, `audit_company_detach` — kim/ne/kayıt sayısı); düzenleyici "kim değiştirdi" izi silinmez.
- **Yeni uç:** `GET /api/v1/security/audit-chain` (yalnız GLOBAL_ADMIN) → `{supported,total,chain_breaks,hash_breaks,ok}`; doğrulamanın kendisi de audit'e yazılır (`audit_chain_verified`).
- Sağlık verisi ayrıca: `HealthRecordRevision` + `HealthAccessLog` (kendi append-only trigger'ları; purge'da kontrollü geçici kapatma deseni — `osgb_purge.py`).
- Operasyonel log: `StructuredAccessLogMiddleware` + `RequestIdMiddleware` (request-id korelasyon).
- Testler: `test_audit_chain.py` (3), `test_osgb_purge.py` regresyonu yeşil.

---

## 3) ÇSGB İBYS Veri Setleri ve E-İmza

### a) Eğitim Veri Seti
| İBYS parametresi | Karşılığı | Durum |
|---|---|---|
| TCKN doğrulama | `validation_tr` (TC kimlik algoritması) + masked saklama | ✅ |
| Eğitim kategorisi/konu | `training_nace` sınıflandırma + konu katalogları + soru bankası (NACE 2026) | ✅ |
| Tarih/süre | `TrainingSession` tarih + süre alanları; geçerlilik hesapları (`test_training_validity`) | ✅ |
| Yöntem (yüz yüze/uzaktan) | classroom + `remote_training` modülü (video, ilerleme, sınav, politika gate'leri) | ✅ |
| Eğitici/eğitilen + sertifika | katılımcı kayıtları, eğitmen modu, sertifika PDF + QR `trainings/verify/{code}` | ✅ |
| Eğitici TCKN bağlantısı | `TrainingSession.instructor_professional_id` + ayrı şifreli `ProfessionalRegulatoryIdentity`; tam TCKN yalnız authority adapter içinde çözülür | ✅ |
| Eski eğitim eğitici backfill | Yönetici Eğitim Kayıtları ekranında readiness matrisi; aynı OSGB + birebir ad-soyad eşleşmesi dışında otomatik bağlama yok, belirsiz kayıt manuel inceleme | ✅ |
| Resmî JSON/XML şeması | Resmî sözleşme bekliyor — `katip-prep/export.csv` + `ibys-export/package` veri hazırlığı mevcut | ⛔ sözleşme |

### b) Sağlık Gözetimi Veri Seti
- `HealthRecord`: odyometri (tarih+sonuç), spirometri/SFT, akciğer grafisi, kan kurşunu (değer/birim/ref/eval), diğer biyolojik testler, maruziyetler, önerilen tetkikler, bilgilendirilmiş onay (+tarih), kısıtlamalar, takip notu, hekim bağlantısı (`physician_professional_id`), `fitness_status` (işe elverişlilik kanaat enum'ı) + `form.html`/`fitness.html` çıktıları + rapor dosyası. ✅
- Anamnez: yapılandırılmış alanlar eklendi: kronik hastalık, geçmiş tıbbi/cerrahi öykü, aile öyküsü, ilaç, alerji, sigara + paket-yıl, alkol, mesleki geçmiş, geçmiş maruziyet ve güncel yakınma. Eski `summary`/`exposures` kayıtları geriye uyum için korunur. ✅
- Hekim değerlendirmesi: `diagnosis` ve `laboratory_result_summary` ayrı alanlar olarak eklendi. ✅
- Sağlık Excel çıktısı: tanı, laboratuvar özeti ve yapılandırılmış anamnez alanları sağlık gözetimi dışa aktarımına eklendi; revizyon snapshot'ı model kolonlarını dinamik aldığı için 0125 alanları hash-zincirli geçmişe dahildir. ✅
- Gizlilik: alan bazlı şifreleme production'da açık (`HEALTH_FIELD_ENCRYPTION_ENABLED=true`), revizyon + erişim logu, hekim rolü scoping (`require_roles_or_workplace_manager`). ✅
- Laboratuvar/tetkik kaydı: `WorkplaceMeasurement` (limit_value, lab_name, report_ref). ✅

### c) Tehlike Kaynakları Veri Seti
- `HazardCategory`/`Hazard` kataloğu (fiziksel/kimyasal/biyolojik/ergonomik — `hazard_seed`), mevzuat referansları, AI öneri alanları. ✅
- `RiskAssessment`: 5x5 / Fine-Kinney / HAZOP yöntemleri, olasılık×şiddet(+frekans) skor, kalıntı risk, süre/termin, DoF aksiyonları, GPS/bölüm/şube bağlamı. ✅
- Maruz kalan kişi: `affected_people`/`affected_group` (metin) + **YENİ `exposed_worker_count` (0123)** — sayısal İBYS alanı; create/update/response/revizyon zincirine kablolandı, testli. ✅
- Kimyasal: `ChemicalProduct` + SDS register (`sds.py`) + PKD register (0120). ✅

### E-İmza (5070)
- Orkestrasyon: `esign_orch.py` (request → tek kullanımlık token/hash → nonce `secrets.compare_digest` → complete/verify) + lokal **PKCS#11 imza ajanı** (`tools/isg-suite-signer`, `qualified=true` yalnız akıllı kart modunda) + demo-PFX ayrımı.
- Ağ doğrulama flag'leri: `ESIGN_OCSP_ENABLED/CRL/TSA_URL` (varsayılan kapalı — güvenli).
- **Eksik (kullanıcı tarafı):** gerçek QES sertifika/smart-card tedariki ve TSA URL temini; kod tarafı hazır, mock imza "qualified" sayılmaz. ✅(kod)/⛔(tedarik)

---

## 4) Siber Güvenlik Sertleştirme (özet)

Ayrıntı: `isg-suite-osgb-guvenlik-raporu.md` + `isg-suite-osgb-retest.csv` (bulgu F-01..F-09, canlı doğrulamalar).

- RBAC: `require_roles` + tenant scope (`tenant_access`, membership tabloları, `test_tenant_isolation*`). ✅
- Rate-limit: global 120rpm + auth 30rpm, XFF spoof koruması (`proxy_trust_depth`), Redis hazır (`redis==5.2.1`; URL verilince otomatik paylaşım — F-06 scaffold). ✅
- Cryptography: bcrypt, JWT HS (PyJWT, algoritma sabitleme, jti denylist, token_version), Fernet (MFA), alan bazlı sağlık şifreleme, yedek şifreleme, constant-time karşılaştırmalar. ✅
- In-Transit: TLS 1.3 yalnız (canlı doğrulandı 2026-09-21), HSTS preload (API), eski TLS reddi. ✅ — istisna: SMTP/POP3 sağlayıcı engeli (F-01, Brevo paketi hazır).
- Upload güvenliği: gateway + magic-byte + uzantı/boyut limitleri; ClamAV scaffold hazır (F-05, provision bekliyor).
- Canlı kapı doğrulaması (2026-09-21): docs 404, private uçlar 401, CORS allowlist, hatada sızıntı yok, QR şema koruması 400. ✅

---

## 5) Doğrulama Kanıtları (bu revizyon)

- Yeni testler: `test_audit_chain.py` (3), `test_risk_exposed_count.py` (5) → **8/8 geçti**.
- Regresyon: `test_osgb_purge.py` + `test_token_revoke.py` + `test_risk_validity.py` + `test_risk_scoring_thresholds.py` → **35/35 geçti**.
- Migration zinciri: `0121 → 0122 → 0123 → 0124 → 0125`; production açılışta `alembic upgrade head` (start.sh, başarısızsa **başlamayı reddeder**).
- CI: push sonrası GitHub Actions (backend pytest + PG matris + security workflow).

## 6) Üretim Öncesi Kalan Dış Bağımlılıklar (kodla çözülemez)

| # | Kalem | Sorumlu aksiyon |
|---|---|---|
| 1 | SMTP TLS (F-01) | Brevo hesabı + domain auth → `SECURITY_INFRA_ROLLOUT.md` §1 |
| 2 | Resmî İBYS/KATİP sözleşmesi + test kodları | ÇSGB başvurusu; sonrasında adapter contract testleri |
| 3 | QES akıllı kart/sertifika + TSA | Tedarik; signer agent PKCS#11 hazır |
| 4 | ClamAV servisi (F-05) | Provision → `CLAMAV_REQUIRED=true` |
| 5 | Redis KV (F-06) | Render Key Value → `REDIS_URL` |
| 6 | F-09 statik header | Render Dashboard → Blueprint Sync |
| 7 | Deploy sonrası | Global admin ile `GET /api/v1/security/audit-chain` → `ok=true` doğrula |
