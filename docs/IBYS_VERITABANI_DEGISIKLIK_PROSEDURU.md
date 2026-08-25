# İBYS Veritabanı Değişiklik Prosedürü

**Doküman sürümü:** 1.0
**Tarih:** 26 Ağustos 2026
**Sahibi:** [Firma adı doldurulacak]
**İlgili standart:** ÇSGB İBYS Başvuru Formu #6 — "Uygulamayı kullanan kişi ve firmalardan
gelen veritabanında yapılması istenilen veri değişikliği taleplerinin ne şekilde
yönetileceği. (Değişiklik talepleri veri sahibinden yapılmalıdır.)"

---

## 1. Amaç ve Kapsam

Bu prosedür, İSG Suite OSGB uygulamasında tutulan verilerde müşteri/işveren/OSGB
tarafından talep edilen değişikliklerin nasıl alındığını, doğrulandığını,
uygulandığını ve denetlendiğini tanımlar.

**Temel ilke:** Veritabanında değişiklik yalnızca **veri sahibi** tarafından veya veri
sahibinin yazılı yetki verdiği kişi tarafından talep edilebilir. Üçüncü tarafların
(çalışan, başka OSGB) veri sahibi adına talebi, veri sahibi onayı olmadan kabul edilmez.

## 2. Roller

| Rol | Sorumluluk |
|---|---|
| Veri sahibi (işveren/OSGB yetkilisi) | Değişiklik talebinin kaynağı; kimliği doğrulanır |
| Sistem yöneticisi | Teknik uygulama, migration, veri bütünlüğü |
| OSGB yöneticisi | Kapsamı içindeki veriler için onay ve uygulama |
| İSGGM (ÇSGB) | Mevzuat gereği değişiklik talebi/uygulama denetimi |

## 3. Değişiklik Talebi Alma

1. **Kanal:** Talepler yalnızca kimliği doğrulanmış kanaldan alınır:
   - Platform içi destek talebi (login olmuş kullanıcının hesabından)
   - Kurumsal e-posta (kayıtlı yetkili kişinin adresinden) + imza/kaşe
   - Resmi yazı (kaşe/imza)
2. **Kimlik doğrulama:** Talebi yapan kişinin veri sahibi olduğu teyit edilir
   (kayıtlı yetkili kişi eşleşmesi). Başkası adına talepte yetki belgesi istenir.
3. **Kayıt:** Her talep benzersiz kimlik (UUID) ile kaydedilir; talep metni, talep
   tarihi, talep eden kimlik ve doğrulama kanalı loglanır.

## 4. İzin Verilen Değişiklik Tipleri

| Tip | Örnek | Yöntem |
|---|---|---|
| Düzeltme (veri sahibi hatası) | Çalışan adı/TCKN düzeltme | Platform arayüzü (rol bazlı) |
| Silme/hesap kapatma | Çalışan ayrılma, KVKK silme | Platform + onay akışı |
| Toplu veri taşıma | Excel içe aktarma | `employee_excel.py`, önizleme + onay |
| Şema/altyapı değişikliği | Yeni alan, enum | Alembic migration (bkz. Bölüm 6) |
| Tenant veri taşıma | OSGB'ye firma devri | Yalnız veri sahibi onayıyla |

## 5. Değişiklik Uygulama Akışı

1. **Onay:** Talep veri sahibi tarafından doğrulandıysa → OSGB yöneticisi/platform
   onayı (rol bazlı `require_roles`).
2. **Önizleme/Dry-run:** Toplu değişikliklerde önce önizleme; hatalı satır listesi
   kullanıcıya gösterilir, onaylanmadan uygulanmaz.
3. **Uygulama:** Değişiklik uygulama katmanından (API) yapılır; doğrudan DB erişimi
   yoktur. Tüm değişiklik `audit_logs`'a yazılır (kullanıcı, IP, aksiyon, eski/yeni).
4. **Doğrulama:** Değişiklik sonrası veri bütünlüğü ve RLS kapsamı kontrol edilir.
5. **Bildirim:** Veri sahibine değişiklik tamamlandığına dair bildirim gönderilir.

## 6. Şema/Veritabanı Yapı Değişikliği (Alembic)

- **Tüm şema değişiklikleri versiyonlanmıştır:** `backend/alembic/versions/` (98+
  migration). Manuel SQL değişikliği yasaktır.
- **Migration akışı:** Geliştirme → code review → staging'te `alembic upgrade head`
  testi → production. Geri alınamayan (destructive) migration'larda önce yedek alınır.
- **RLS uyumu:** Her yeni tablo/alan migration'ı RLS policy ile gelir
  (`backend/alembic/versions/0043_rls_legal_acceptances.py` örneği).
- **Regülatör veri ön kontrolü:** `regulatory_data_preflight.py` İBYS başvurusu
  öncesi veri kalitesini kontrol eder; eksik/yanlış veri tespit ederse engeller.

## 7. Reddedilen/Yetkisiz Talepler

- Veri sahibi olmayan kişinin talebi → reddedilir, gerekçe loglanır.
- Başka tenant'ın verisi için talep → reddedilir (RLS, `ensure_company_access`).
- Mevzuata aykırı (ör. geriye dönük sahte kayıt) → reddedilir, denetime bildirilir.
- Gizlilik Sözleşmesi 3.8 ve 3.14 gereği, yetkisiz kişilere veri değişikliği/aktarma
  yapılamaz.

## 8. Denetim ve İzleme

- Tüm değişiklikler `audit_logs` tablosunda (kullanıcı, IP, aksiyon, zaman damgası,
  eski/yeni değer) saklanır. KVKK md.12 (veri işleyenin sorumluluğu) kapsamında
  izlenebilirlik sağlanır.
- OSGB yöneticisi kendi kapsamındaki değişiklik geçmişini görüntüleyebilir
  (`/api/v1/security/audit-logs`, rol bazlı).
- ÇSGB/İSGGM denetiminde değişiklik talebi kayıtları, onaylar ve audit log sunulur.

## 9. Özel Nitelikli Veriler

- **Sağlık verisi:** Yalnız yetkili hekim/DSP rolü değiştirebilir; `confidential_note`
  yalnız hekim erişimli (`health.py` rol kontrolü).
- **Kimlik (TCKN/YKN):** Şifreli vault'ta; tam değer uygulama katmanından döndürülmez
  (`regulatory_identity_vault.py`). Düzeltme yalnız veri sahibi onayıyla.
- **ÇSGB'ye bildirim verisi:** İBYS/İSG-KATİP gönderiminde değişiklik/düzeltme,
  ilgili metot sözleşmesine göre yapılır (bkz. `ibys_client.py`, `katip_client.py`).

## 10. Referanslar

- Kod: `backend/alembic/versions/`, `backend/app/services/regulatory_data_preflight.py`,
  `backend/app/api/company_access.py`, `backend/app/api/security.py` (audit-logs)
- RLS: `backend/app/core/rls.py`, `backend/app/core/tenant_context.py`
- Gizlilik Sözleşmesi: md.3.8 (veri aktarım yasağı), md.3.12 (veri sahipliği),
  md.3.14 (ticarete konu edilemez), Başvuru Formu #6
