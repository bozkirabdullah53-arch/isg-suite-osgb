# İBYS Entegratör Başvuru Demo ve Kabul Senaryoları

Bu senaryolar resmî Bakanlık kabul testlerinin yerine geçmez. İlk başvuru görüşmesinde sistemin veri güvenliği ve entegrasyona hazır mimarisini göstermek için hazırlanmıştır.

## D-01 — Aday profil kataloğu

**Adım:** `GET /api/v1/ibys-application/profile`

**Beklenen:**

- Profil sürümü `application-candidate-v1`.
- `official_compliance_claim=false`.
- 12 aday veri seti.
- Her veri setinde iç kaynak alanı ve demo zorunluluğu.
- Resmî kod/alanlar boş ve sözleşme bekliyor olarak görünür.

## D-02 — Geçerli işyeri kaydı

**Veri seti:** `workplace`

**Girdi:** Kaynak id, işyeri adı, SGK sicil no, NACE kodu, tehlike sınıfı ve aktiflik alanları dolu tek kayıt.

**Beklenen:**

- `accepted_count=1`
- `rejected_count=0`
- `valid=true`
- Kayıt fingerprint’i SHA-256 biçiminde.

## D-03 — Eksik zorunlu alan

**Girdi:** NACE kodu ve tehlike sınıfı olmayan işyeri kaydı.

**Beklenen:**

- Kayıt reddedilir.
- Ret raporu yalnız kayıt sırası, fingerprint ve eksik alan adlarını içerir.
- SGK sicil no veya diğer hassas içerik ret raporuna kopyalanmaz.

## D-04 — Deterministik fingerprint

**Girdi:** Aynı iş kaydı, farklı `updated_at` zamanlarıyla iki kez doğrulanır.

**Beklenen:** Fingerprint aynıdır; geçici zaman alanları iş kimliğini değiştirmez.

## D-05 — Mükerrer gönderim koruması

**Adım:** Aynı OSGB ve aynı kayıt kümesi için iki aday zarf üretilir.

**Beklenen:** `idempotency_key` aynıdır.

**Kontrol:** Kayıt içeriği veya OSGB kapsamı değişirse anahtar değişir.

## D-06 — OSGB kapsam ihlali

**Adım:** OSGB yöneticisi başka bir OSGB id ile zarf üretmeyi dener.

**Beklenen:** HTTP 403; paket üretilmez.

## D-07 — Bilinmeyen veri seti

**Adım:** Tanımsız veri-seti koduna doğrulama isteği gönderilir.

**Beklenen:** HTTP 400 ve standart hata mesajı; harici ağ çağrısı yapılmaz.

## D-08 — Büyük paket sınırı

**Adım:** 1000 kayıtlık aday paket doğrulanır; 1000 üzeri istek denenir.

**Beklenen:** 1000 kayıt işlenir; üst sınır Pydantic doğrulamasıyla reddedilir.

## D-09 — Tenant veritabanı izolasyonu

**Adım:** NOBYPASSRLS test rolü ile iki OSGB kaydı hazırlanır ve tenant bağlamı uygulanır.

**Beklenen:** Kullanıcı yalnız kendi tenant satırlarını görür; 47 kritik tabloda RLS + FORCE RLS korunur.

## D-10 — Secret gizliliği

**Adım:** Eksik credential ve ağ hata senaryoları çalıştırılır.

**Beklenen:** API URL, token, sertifika veya secret yanıta/loga yazılmaz.

## D-11 — Resmî sözleşme uyarlama provası

**Adım:** Test amaçlı yeni bir profil sürümünde bir veri-setine resmî kod ve alan adları eklenir.

**Beklenen:** Eski aday profil değişmeden kalır; yeni sürüm ayrı yayımlanır ve envelope profil sürümünü taşır.

## D-12 — Bakanlık ortamı geldiğinde zorunlu testler

Aşağıdaki senaryolar resmî endpoint ve hata kataloğu olmadan tamamlanmış sayılmaz:

- Geçerli kayıt kabulü
- Eksik zorunlu alan reddi
- Geçersiz kod listesi reddi
- Mükerrer kayıt davranışı
- Kısmi paket kabulü
- Yetkisiz/sertifikası süresi dolmuş istemci
- Timeout ve tekrar deneme
- Bakanlık işlem/referans numarası doğrulaması
- Gönderim sonrası durum sorgulama/mutabakat
