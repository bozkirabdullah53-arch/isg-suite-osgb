# Dijital Personel Kartı — Mevcut Sistem Analiz Raporu

**Durum:** Faz 1 / yalnız okuma ve mimari analiz  
**Production etkisi:** Yok  
**Migration:** Yok  
**Feature flag değişikliği:** Yok  
**Temel kural:** Çalışan hiçbir personel, profesyonel, kullanıcı, eğitim, kurul, risk, PDF, R2, onay, imza veya bildirim akışı bozulmayacaktır.

## 1. Amaç ve analiz sınırı

Bu rapor, Dijital Personel Kartı / Profesyonel Personel Profili modülü geliştirilmeden önce mevcut sistemin gerçek veri akışını ve korunması gereken sözleşmeleri çıkarır.

Bu fazda:

- Kod davranışı değiştirilmez.
- Veritabanı şeması değiştirilmez.
- Mevcut kayıtlar dönüştürülmez veya birleştirilmez.
- Production ayarları değiştirilmez.
- Hassas veya özel nitelikli veri toplamaya başlanmaz.
- Personel kartı kullanıcıya açılmaz.

## 2. İncelenen ana dosyalar

### Backend

- `backend/app/models/entities.py`
- `backend/app/schemas/employee.py`
- `backend/app/schemas/osgb.py`
- `backend/app/api/employees.py`
- `backend/app/api/osgb.py`
- `backend/app/api/company_access.py`
- `backend/app/api/deps.py`
- `backend/app/core/config.py`
- `backend/app/core/tenant_context.py`
- `backend/app/services/employee_excel.py`
- `backend/app/services/object_store.py`
- `backend/app/services/upload_gateway.py`
- `backend/app/services/upload_security.py`
- `backend/app/services/audit.py`
- `backend/app/services/professional_duty.py`
- `backend/app/main.py`

### Frontend

- `frontend/src/main.jsx`
- `frontend/src/osgb.jsx`
- `frontend/src/api.js`
- `frontend/src/styles.css`
- `frontend/src/theme-modern.css`
- `frontend/src/ui_modal.jsx`

### Test ve operasyon

- `backend/tests/test_object_store.py`
- `backend/tests/test_ci_postgres_parity.py`
- `backend/scripts/qa_api_smoke.py`
- `backend/scripts/qa_crud_smoke.py`
- `backend/scripts/qa_upload_export_smoke.py`
- `.github/workflows/ci.yml`

## 3. Mevcut personel veri yapıları

Sistemde “personel” tek bir tablo değildir. En az üç ayrı kimlik alanı vardır ve bunların zorla birleştirilmesi geriye dönük uyumluluğu bozar.

### 3.1 `Employee` — işyeri çalışanı

`employees` tablosu işyerindeki çalışanları temsil eder.

Mevcut alanlar:

- `id`
- `company_id`
- `branch_id`
- `full_name`
- `national_id_masked`
- `job_title`
- `department`
- `start_date`
- `special_status`
- `is_active`

Mevcut davranış:

- Şirket ve şube ilişkisi vardır.
- Tekli personel ekleme desteklenir.
- Excel içe aktarma desteklenir.
- Silme fiziksel silme değildir; `is_active=false` yapılır.
- Toplu silme de güvenli pasife alma biçimindedir.
- Arama ad, görev ve departmanda çalışır.

Koruma kararı:

- Bu tablo yeniden yazılmayacaktır.
- Excel içe aktarma sözleşmesi kırılmayacaktır.
- Yeni profil modülü `Employee` kaydını genişleten ayrı bir katman olacaktır.

### 3.2 `IsgProfessional` — OSGB profesyoneli

`isg_professionals` tablosu şu üç temel profesyonel türünü temsil eder:

- İş Güvenliği Uzmanı
- İşyeri Hekimi
- Diğer Sağlık Personeli

Mevcut alanlar:

- `id`
- `osgb_id`
- `full_name`
- `email`
- `phone`
- `professional_type`
- `certificate_class`
- `certificate_number`
- `certificate_date`
- `is_active`
- `created_at`

Mevcut davranış:

- Profesyonel eklenince giriş hesabı oluşturulabilir veya mevcut hesap bağlanır.
- Profesyonel, e-posta öncelikli; gerekli durumda ad eşleşmesiyle kullanıcı hesabına bağlanır.
- Askıya alma ve yeniden aktifleştirme vardır.
- Aktif görevlendirmesi bulunan profesyonel fiziksel olarak silinemez.
- Bağlı geçmiş kayıtlar nedeniyle fiziksel silme başarısızsa askıya alınır.

Koruma kararı:

- Profesyonel kayıtları `Employee` tablosuna taşınmayacaktır.
- Mevcut giriş hesabı oluşturma ve eşleme davranışı değiştirilmeden korunacaktır.
- Yeni profil kartı mevcut profesyonel kimliğini referans alacaktır.

### 3.3 `User` — uygulama giriş hesabı ve yetki

`users` tablosu giriş kimliğini ve uygulama rolünü taşır.

Mevcut roller:

- `global_admin`
- `company_admin`
- `safety_specialist`
- `workplace_physician`
- `other_health_personnel`
- `read_only`

Kritik ayrım:

- Uygulama rolü bir mesleki yeterlilik değildir.
- “Patlamadan korunma dokümanı hazırlama yeterliliği” gibi uzmanlıklar login rolüne dönüştürülmemelidir.
- Yeni yeterlilik/uzmanlık kayıtları ayrı mesleki veri olarak tutulmalıdır.

### 3.4 `WorkplaceAssignment` — profesyonel görevlendirme geçmişi

`workplace_assignments` tablosu profesyoneli şirkete bağlar ve tarihsel görev ilişkisini taşır.

Önemli alanlar:

- `osgb_id`
- `company_id`
- `professional_id`
- `professional_type`
- `start_date`
- `end_date`
- aylık zorunlu/planlanan/fiili süreler
- İSG-KATİP sözleşme numarası
- sözleşme dosya meta alanları
- durum

Koruma kararı:

- Personel kartında görev geçmişi bu tablodan salt okunur özetlenebilir.
- Mevcut görevlendirme tablosu CV veya profil için kopyalanıp değiştirilmez.
- Gizli müşteri içeriği dış paylaşım paketine otomatik eklenmez.

## 4. Mevcut frontend akışı

### 4.1 Personel Yönetimi

`frontend/src/main.jsx` içinde `Employees` bileşeni vardır.

Mevcut özellikler:

- Zorunlu işyeri seçimi
- İsteğe bağlı şube seçimi
- Arama
- Tekli personel ekleme
- Excel şablonu indirme
- Excel yükleme
- Excel raporu indirme
- Tekli ve toplu güvenli pasife alma

Mevcut tabloda şu an profil/detay açma eylemi yoktur.

Koruma kararı:

- Mevcut tablo ve butonlar yeniden yazılmayacaktır.
- Gelecekte yalnız eklemeli bir “Personel Kartını Aç” eylemi eklenecektir.
- Feature flag kapalıyken bu eylem görünmeyecek ve mevcut ekran birebir çalışacaktır.

### 4.2 İSG Profesyonelleri

`frontend/src/osgb.jsx` içinde `ProfessionalsPage` bileşeni vardır.

Mevcut özellikler:

- Uzman, hekim ve DSP sekmeleri
- Aktif/askıda/tümü filtreleri
- Arama
- Yeni profesyonel oluşturma
- Düzenleme
- Askıya alma/aktifleştirme
- Güvenli silme
- Kullanıcı hesabı oluşturma/bağlama
- Performans ve saha takvimine geçiş

Koruma kararı:

- Bu sayfa personel kartıyla değiştirilmez.
- Liste yönetim ekranı olarak kalır.
- Yeni kart ayrı bir sayfa/izole panel olur.

## 5. Mevcut API sözleşmeleri

### 5.1 Çalışan API’leri

Korunacak yollar:

- `GET /api/v1/employees`
- `POST /api/v1/employees`
- `PUT /api/v1/employees/{employee_id}`
- `DELETE /api/v1/employees/{employee_id}`
- `POST /api/v1/employees/bulk-delete`
- `GET /api/v1/employees/import-template.xlsx`
- `POST /api/v1/employees/import-excel`

Yeni kart API’leri bu yolları değiştirmeyecek; ayrı `/personnel-profiles/...` sınırında eklenecektir.

### 5.2 Profesyonel API’leri

Korunacak yollar:

- `GET /api/v1/osgb/professionals`
- `POST /api/v1/osgb/professionals`
- `PATCH /api/v1/osgb/professionals/{professional_id}`
- `PATCH /api/v1/osgb/professionals/{professional_id}/suspend`
- `PATCH /api/v1/osgb/professionals/{professional_id}/activate`
- `DELETE /api/v1/osgb/professionals/{professional_id}`
- mevcut performans ve görevlendirme yolları

Yeni profil kartı mevcut yanıt şemalarına zorunlu alan eklemeyecektir.

## 6. Yetkilendirme ve tenant sınırı

Mevcut sistem:

- `ensure_company_access` ile şirket erişimini doğrular.
- Saha rolleri için aktif `WorkplaceAssignment` kayıtlarından erişilebilir şirketleri çıkarır.
- `WorkplaceMembership` erişimi eklemeli olarak genişletebilir.
- `TenantContext` bulunduğunda OSGB çapraz erişimini ikinci kez keser.
- Profesyonel kullanıcı eşlemesinde e-posta önceliklidir; OSGB sınırı olmadan ad eşleşmesi yapılmaz.

Yeni modül için zorunlu yaklaşım:

- Frontend rolüne güvenilmeyecek.
- Her profil ve dosya isteğinde backend tekrar doğrulayacak:
  - kullanıcı
  - gerçek rol
  - OSGB kapsamı
  - şirket kapsamı
  - işyeri/şube kapsamı
  - profil öznesi
  - belge sınıfı
  - işlem amacı
  - kayıt durumu
- Müşteri şirket kullanıcıları tam karta doğrudan erişemeyecek.
- Profesyonel kendi profilini görme desteği ayrı ve açık ilişki üzerinden kurulacak; yalnız ad benzerliği yeterli olmayacak.

## 7. Dosya yükleme ve object storage

### 7.1 Mevcut object-store katmanı

`backend/app/services/object_store.py` şu modları destekler:

- local
- dual
- S3/R2 uyumlu uzak depolama

Mevcut güvenlik özellikleri:

- path traversal engelleme
- S3 yüklemesi sonrası boyut doğrulama
- dual modda uzak yazma hatasında isteğe bağlı atomik rollback
- eski local dosyaya geriye dönük okuma fallback’i
- mevcut `get_object_store()` soyutlaması

Yeni modül:

- Doğrudan `Path.write_bytes` kullanmayacak.
- Yalnız `get_object_store()`/mevcut upload gateway üzerinden çalışacak.
- Nesne anahtarlarında isim, TCKN, telefon, e-posta, sağlık veya adli sicil bilgisi bulunmayacak.
- Dosyalar private-by-default olacak.
- İndirme backend yetkilendirmesi ve kısa ömürlü erişim üzerinden yapılacak.

### 7.2 Mevcut upload güvenliği

`assert_safe_upload`:

- uzantı ve magic-byte eşleşmesi yapar
- EXE/ELF/script imzalarını reddeder
- PDF, resim, XLSX, DOCX ve bazı ofis türlerini tanır
- ClamAV yapılandırılmışsa tarama yapar
- reddedilen içeriği karantinaya alabilir

Yeni profil dosyaları için ek zorunluluklar:

- kategori bazlı boyut sınırı
- gerçek MIME doğrulaması
- fotoğrafta yeniden kodlama/crop sonrası güvenli çıktı
- DOCX/PDF CV ayrı izin listesi
- çift tıklama/idempotency koruması
- checksum
- başarısız yüklemede geçerli DB kaydı bırakmama

## 8. Audit ve bildirim altyapısı

### 8.1 Audit

`add_audit_log` servisi kullanıcı, şirket, eylem, varlık türü, varlık kimliği, açıklama, IP, modül ve değişiklik özeti kaydedebilir.

Mevcut `employees` API’sinde tüm işlemlerin bu servisi kullandığı görülmemektedir. Yeni profil modülünde audit çağrıları servis sınırında zorunlu olacaktır.

Loglarda bulunmayacak içerikler:

- dosya gövdesi
- tam TCKN
- sağlık ayrıntısı
- adli sicil içeriği
- R2 secret veya token
- kalıcı imzalı URL

### 8.2 Bildirim

Mevcut sistemde görev/termin uyarıları üreten altyapı ve bildirim modelleri vardır. Ancak personel belge sürelerini 90/60/30/15/7 gün eşiklerinde yöneten genel bir personel belge zamanlayıcısı doğrulanmamıştır.

Bu özellik ayrı fazda, mevcut bildirim altyapısını genişleterek ve belge içeriğini bildirim alıcısına sızdırmadan uygulanmalıdır.

## 9. PDF ve CV durumu

Sistemde çeşitli PDF üretim servisleri ve ReportLab kullanımı vardır; ancak doğrulanmış, sürümlemeli bir personel CV modeli ve personel CV renderer’ı bulunmamaktadır.

Yeni CV renderer:

- onaylı alan manifestinden üretilecek
- A4 olacak
- Türkçe karakterleri destekleyecek
- her üretimde sürüm ve hash kaydedecek
- sağlık, adli sicil, tam TCKN, ev adresi, acil kişi, maaş ve disiplin verilerini otomatik dışlayacak
- üretim öncesinde kullanıcıya alan düzeyinde önizleme gösterecek

## 10. Mevcut hukuki ve teknik riskler

### R1 — `national_id_masked` alanında tam TCKN bulunabilmesi

Alan adı maskeli olmasına rağmen mevcut Excel şablonu ve içe aktarma servisi 11 haneli TCKN örneğini aynı alana yazabilmektedir.

Risk:

- Alan adının sağladığı güvenlik varsayımı gerçek veriye uymayabilir.
- Mevcut API yanıtı bu değeri yetkili rollerin tümüne döndürebilir.

Karar:

- Bu fazda değiştirilmez; çalışan import akışı korunur.
- Ayrı veri envanteri ve dönüşüm planı gerekir.
- Yeni profil API’si bu alanı ham biçimde tekrar etmeyecek; varsayılan maskeli cevap verecektir.

### R2 — `special_status` alanı özel nitelikli/hassas bilgi içerebilir

Excel şablonunda “Engelli/Hükümlü Durumu” aynı genel personel kaydına alınmaktadır.

Risk:

- Engellilik sağlık/özel nitelikli veri bağlamına girebilir.
- Hükümlülük/adli sicil bağlamı sıradan profil verisi olmamalıdır.
- Mevcut personel listesindeki geniş rol erişimi bu alan için aşırı olabilir.

Karar:

- Yeni kart bu alanı varsayılan özet veya CV’ye dahil etmeyecektir.
- Yeni “adli sicil belgesi yükle” alanı açılmayacaktır.
- Hukuki dayanak, amaç, saklama süresi ve rol matrisi onaylanmadan restricted-data işleme kapalı kalacaktır.
- Mevcut alanın güvenli dönüşümü ayrı hukuk/retention görevidir.

### R3 — `Employee`, `IsgProfessional` ve `User` arasında tekil bağ yok

Risk:

- Aynı kişi üç farklı kayıtta bulunabilir.
- Ad/e-posta eşleşmesi yanlış kişiye bağlanma riski taşır.
- Otomatik merge tarihsel kayıtları bozabilir.

Karar:

- Otomatik birleştirme yapılmayacaktır.
- Ayrı profil öznesi ve açık bağlama kaydı kullanılacaktır.
- Belirsiz eşleşme yönetici onayı olmadan yapılmayacaktır.

### R4 — Profesyonel fiziksel silme davranışı

Aktif görevlendirme yoksa profesyonel fiziksel olarak silinebilmektedir; bağlı geçmiş varsa soft-delete fallback’i vardır.

Risk:

- Yeni profil/dosya ilişkileri fiziksel silme davranışını etkileyebilir.

Karar:

- Yeni profile bağlanan profesyoneller için geçmiş korunmalıdır.
- Mevcut delete endpointi bu fazda değiştirilmez.
- Model fazında FK davranışı `RESTRICT/SET NULL` ve arşivleme etkisiyle ayrıca test edilir.

### R5 — Object storage production modu kesin olarak varsayılmamalı

Kod local/dual/R2 destekler; fakat yalnız kod incelemesiyle aktif production backend ve uzak zorunluluk durumu kesin kabul edilmemelidir.

Karar:

- Dosya yükleme fazından önce secret göstermeyen durability/readiness sonucu doğrulanır.
- Uzak kalıcı depolama zorunlu değilse personel dosya özelliği production’da açılmaz.

## 11. Önerilen izole mimari

Mevcut tablolar değiştirilmeden yeni uzantı katmanı önerilir.

### 11.1 Profil öznesi

Yeni `personnel_profiles` tablosu:

- `id`
- `osgb_id`
- `company_id` nullable
- `branch_id` nullable
- `employee_id` nullable
- `professional_id` nullable
- `user_id` nullable
- `profile_type`
- `status`
- `version`
- `created_by_id`
- `created_at`
- `updated_at`
- `archived_at`

Kural:

- Bir profilin ana öznesi açıkça belirlenir.
- `Employee` ve `IsgProfessional` kayıtları yerinde kalır.
- Otomatik merge yoktur.
- Tenant alanları profil üzerinde ayrıca bulunur; her sorguda doğrulanır.

### 11.2 Eklemeli alt tablolar

Önerilen ayrı tablolar:

- `personnel_profile_contacts`
- `personnel_profile_competencies`
- `personnel_profile_experiences`
- `personnel_profile_documents`
- `personnel_profile_document_versions`
- `personnel_profile_cv_versions`
- `personnel_profile_shares`
- `personnel_profile_share_items`
- `personnel_profile_access_events`
- `personnel_profile_retention_rules`
- restricted-data için ayrı ve varsayılan kapalı tablolar

Hiçbiri mevcut çalışan tabloların alanlarını yeniden adlandırmaz veya taşımayı zorunlu kılmaz.

## 12. Feature flag ve rollout ilkesi

Önerilen ayarlar:

```text
PERSONNEL_PROFILE_CARD_ENABLED=false
PERSONNEL_PROFILE_CARD_FORCE_OFF=false
PERSONNEL_PROFILE_CARD_PILOT_COMPANY_IDS=
PERSONNEL_PROFILE_RESTRICTED_DATA_ENABLED=false
PERSONNEL_PROFILE_EXTERNAL_SHARING_ENABLED=false
```

Aktiflik koşulu:

1. global flag açık
2. force-off kapalı
3. şirket pilot allowlist içinde
4. ilgili alt özellik için hukuki/operasyonel readiness tamam

Feature kapalıyken:

- mevcut Personel ekranı aynı kalır
- mevcut İSG Profesyonelleri ekranı aynı kalır
- Excel import/export aynı kalır
- mevcut dosyalar ve atamalar okunur
- yeni profile özel hata eski akışı engellemez

## 13. Önerilen yetki matrisi başlangıcı

| İşlem | Global Admin | OSGB/Company Admin | Uzman | Hekim | DSP | Salt Okunur | Müşteri |
|---|---:|---:|---:|---:|---:|---:|---:|
| Genel profesyonel özeti | Kapsamlı | Kendi kapsamı | Atandığı işyeri / kendi | Atandığı işyeri / kendi | Atandığı işyeri / kendi | Onaylı minimum | Hayır |
| Genel belge meta bilgisi | Auditli | Kendi kapsamı | Gerekli ise | Gerekli ise | Gerekli ise | Hayır | Hayır |
| CV üretme | Yetkili kapsam | Yetkili kapsam | Kendi profili için talep | Kendi profili için talep | Kendi profili için talep | Hayır | Hayır |
| Dış paylaşım paketi | Ayrı yetki | Ayrı yetki | Varsayılan hayır | Varsayılan hayır | Varsayılan hayır | Hayır | Sadece süreli paket |
| Sağlık ayrıntısı | Otomatik değil | Hayır | Hayır | Yasal amaçla ayrı modül | Yasal amaçla sınırlı | Hayır | Hayır |
| Adli sicil/restricted | Otomatik değil | Otomatik değil | Hayır | Hayır | Hayır | Hayır | Hayır |

Bu tablo hukuki ve organizasyonel onay olmadan production yetkisi sayılmaz.

## 14. Durdurma koşulları

Aşağıdaki durumlardan biri varsa ilgili özellik geliştirilmez veya açılmaz:

- veri işleme amacı belirsiz
- hukuki işleme şartı belirlenmemiş
- saklama süresi bilinmiyor
- yetkili roller tanımlı değil
- şirket/işyeri izolasyonu kanıtlanamıyor
- restricted veri ayrımı garanti edilemiyor
- R2/private storage doğrulanamıyor
- migration rollback edilemiyor
- mevcut import, eğitim, kurul, risk, PDF, onay veya imza regresyonu oluşuyor
- mevcut tarihsel kayıt zarar görebilir

## 15. Faz 1 sonucu

Mevcut sistem, yeni modül için kullanılabilecek güçlü yapı taşlarına sahiptir:

- şirket/OSGB kapsam kontrolü
- aktif görevlendirme modeli
- local/dual/R2 object-store soyutlaması
- upload güvenlik katmanı
- audit servisi
- PDF altyapısı
- responsive ortak UI
- SQLite/PostgreSQL CI ve E2E altyapısı

Ancak güvenli geliştirme için önce şu kararlar zorunludur:

1. Profil öznesi bağlama modeli
2. Alan düzeyinde veri sınıflandırması
3. Hukuki amaç/saklama matrisi
4. TCKN ve `special_status` mevcut veri riski planı
5. Restricted veri varsayılan-kapalı mimarisi
6. R2 durability readiness
7. Pilot şirket ve rollback koşulları

Bu rapor tamamlanmadan doğrudan kapsamlı migration veya personel dosyası yükleme özelliği açılmamalıdır.
