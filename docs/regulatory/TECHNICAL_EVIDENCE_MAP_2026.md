# İSG SUITE — İBYS / İSBS Teknik Kanıt Haritası

**Sürüm:** 2026-08-09  
**Amaç:** Başvuru, teknik görüşme ve Bakanlık testinde "bu kontrol nerede uygulanıyor?" sorusuna tekrarlanabilir kaynak kod kanıtı vermek.

| Kontrol | Kaynak / Kanıt | Durum |
|---|---|---|
| OSGB/işyeri erişim kapsamı | `backend/app/api/company_access.py` | Mevcut |
| Request başı tenant context temizliği | `backend/app/core/tenant_middleware.py` | Mevcut |
| Production güvenlik başlıkları | `backend/app/main.py` | Mevcut |
| E‑imza talep + kaynak hash + doğrulama | `backend/app/api/esign.py`, `backend/app/services/esign_pipeline.py` | Mevcut |
| Sağlık hassas alan şifreleme | `backend/app/services/health_field_crypto.py` | Mevcut; dedicated key önerilir |
| Reçete rol/işyeri kontrolü | `backend/app/api/prescriptions.py` | Mevcut |
| Reçete yaşam döngüsü | `backend/app/models/entities.py` | Mevcut |
| Gönderim attempt / hata modeli | `PrescriptionSubmission`, `PrescriptionSubmissionAttempt`, `MedulaErrorLog` | Mevcut |
| Legacy İBYS adapter | `backend/app/services/ibys_client.py` | Stub; resmî sayılmaz |
| İBYS CSV paketi | `backend/app/services/ibys_export.py` | Hazırlık/stub; resmî veri seti sayılmaz |
| Resmî gönderim fail‑closed gate | `backend/app/services/authority_integration_gate.py` | Bu paketle eklendi |
| Gönderim bütünlüğü/idempotency | `backend/app/services/regulatory_submission_envelope.py` | Bu paketle eklendi |
| Resmî kimlik şifreli kasası | `backend/app/models/regulatory_identity.py`, `backend/app/services/regulatory_identity_vault.py` | Bu paketle eklendi |
| Kimlik kasası tenant RLS | `0084_regulatory_identity_vault.py` | Bu paketle eklendi |
| Başvuru readiness raporu | `regulatory_application_readiness.py` | Bu paketle eklendi |
| Veri preflight | `regulatory_data_preflight.py` | Bu paketle eklendi |
| CI/test: fail‑closed ve secret redaction | `test_regulatory_application_readiness.py` | Bu paketle eklendi |

## Güvenlik sınırları

1. Authority access/test code, API secret, encryption key veya tam TCKN loglanmaz ve readiness çıktısında dönmez.
2. Resmî kimlik plaintext'i genel Employee API'sine eklenmez.
3. `RegulatoryIdentity` yalnız adapter içi resolver ile plaintext'e çevrilebilir; public helper maskeli sonuç verir.
4. Legacy `ibys_client.live_send()` varlığı tescil anlamına gelmez; resmî akış yeni authority gate arkasında kurulacaktır.
5. Sağlık Bakanlığı/ÇSGB teknik profilinin bilinmeyen alanları tahmin edilmez.
6. Production send flag test kabulünden/tescilden önce açılmaz.

## Başvuru demosunda gösterilecek kontrollü senaryo

1. Global yönetici readiness raporunu çalıştırır.
2. Applicant-owned dış belgeler ve authority-pending maddeler ayrı görünür.
3. Secret bulunmayan ortamda `assert_authority_send_allowed()` gönderimi reddeder.
4. Sentetik test profilinde secret değerleri raporlanmadan gate açılabilir.
5. Sentetik payload için canonical SHA‑256/idempotency kanıtı gösterilir.
6. Regulatory Identity Vault yalnız maskeli kimlik döndürür.
7. Bakanlık test profili alındığında ayrı adapter wire formatı bu zarfın payload bölümüne eklenir; çekirdek iş modülleri değiştirilmez.

## Başvurudan önce kapatılması gereken operasyonel kalite kapıları

- Clean PostgreSQL migration zinciri yeşil olmalıdır.
- Backend + frontend CI ana kontrolleri yeşil olmalıdır.
- Production sağlık şifreleme anahtarı tercihen dedicated olmalıdır.
- Upload AV, remote storage/backup, OCSP/CRL/TSA ve güçlü oturum konfigürasyonları güvenlik ön denetiminde doğrulanmalıdır.
- Production verisinde legacy alanda tam kimlik numarası bulunmamalıdır; Regulatory Identity Vault migration/backfill planı uygulanmalıdır.
