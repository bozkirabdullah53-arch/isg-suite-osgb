# Yetkili Firma Yönetimi — Uygulama ve İnceleme Raporu

## 1. Sonuç

Bu yükseltme ayrı `feat/authorized-firm-compliance-p0-20260822` dalında, mevcut OSGB/işyeri/profesyonel mimarisini koruyan eklemeli bir modül olarak uygulanmıştır. Production ortamına deploy veya `master` birleşimi yapılmamıştır.

Yeni modül kurum içi firma, belge, profesyonel uygunluğu ve denetim hazırlığı yönetir. Harici gönderim, resmî doğrulama, kabul veya puan aktarımı yapmaz.

## 2. Kapsam ve durum

| Öncelik | Teslim | Durum | Uygulama |
|---|---|---:|---|
| P0 | Yetkili firma kartı ve tarih alanları | Tamamlandı | Tenant-kapsamlı profil modeli, CRUD API ve yönetim ekranı |
| P0 | Tarih tutarlılığı | Tamamlandı | API/Pydantic/DB kontrolleri; görevlendirme–aktif sözleşme dönem eşleşmesi |
| P0 | 30/60/90 gün geçerlilik uyarıları | Tamamlandı | Yetki, zorunlu belge ve profesyonel sertifika uyarıları + bildirim üretimi |
| P0 | Profesyonel belge uygunluğu | Tamamlandı | Rol, sınıf, no, tarihler, zorunlu belgeler, görevlendirme, sözleşme ve dakika kontrolleri |
| P0 | Şeffaf uygunluk skoru | Tamamlandı | 10 kategori; puan/ağırlık/detay/engel/aksiyon ve 24 kayıtlık geçmiş |
| P1 | Çoklu filtre ve durum raporu | Tamamlandı | Konum, aktiflik, tehlike, belge/profesyonel/hazırlık/skor/tarih filtreleri + XLSX |
| P1 | Tek tık firma PDF/Excel dosyası | Tamamlandı | Formül enjeksiyonu engeli ve PDF metin kaçışlama ile |
| P1 | Bildirim ve denetim hazırlık paketi | Tamamlandı | Bildirim taramasına dahil; PDF+XLSX+JSON ZIP paketi |
| P1 | Otomatik eksik listesi | Tamamlandı | Başarısız görünür skor kategorilerinden görev listesi |
| P2 | 11 adımlı onboarding | Tamamlandı | Otomatik durum + yönetici ilerlemesi; tamamlama için 11/11 zorunlu |
| P2 | Kalite, karşılaştırma ve iş yükü | Tamamlandı | 8 kategori kalite skoru, firma sıralaması, dakika dengesi; global-only anonim OSGB kıyası |
| P2 | Denetim Günü modu | Tamamlandı | Yazdırılabilir engel, uyarı ve kontrol listesi görünümü |

## 3. Veri modeli ve migration

Migration `0104_authorized_firm_compliance` dört yeni tablo ekler:

- `authorized_firm_profiles`
- `authorized_firm_documents`
- `professional_compliance_profiles`
- `compliance_score_snapshots`

Değişiklik eklemelidir; mevcut tablo veya kolonları kaldırmaz/dönüştürmez. PostgreSQL'de firma-kapsamlı tablolar `allowed_company_ids`, profesyonel uygunluğu ise `current_osgb_id` RLS bağlamıyla korunur. API katmanı ayrıca OSGB kimliğini doğrular ve tek işyerine bağlı `company_admin`/kiosk hesaplarını OSGB-içi uçlardan çıkarır.

Rollback yalnız bu dört yeni tabloyu ters bağımlılık sırasıyla kaldırır. Production rollback öncesinde PostgreSQL yedeği zorunludur.

## 4. Skor yöntemi

Uygunluk skoru 10 görünür kategorinin eşit ağırlıklı ortalamasıdır: yetki kartı, belge geçerliliği, profesyonel uygunluğu, görevlendirme, ziyaret, risk, düzeltici faaliyet, eğitim, anonim sağlık uyumu ve denetim hazırlığı.

Kalite skoru 8 görünür kategorinin eşit ağırlıklı ortalamasıdır: belge tamlığı, ziyaret, risk kapatma, eğitim, anonim sağlık takibi, profesyonel iş yükü, denetim hazırlığı ve düzeltici faaliyet performansı.

Her kategori yanıtında `score`, `weight`, `detail`, `passed`, `critical` ve `recommended_action` alanları bulunur. `black_box=false` açıkça döndürülür. Skor resmî uygunluk veya makam doğrulaması olarak sunulmaz.

## 5. Mahremiyet ve güvenlik incelemesi

- Firma detayları ve tüm çıktılar sağlık verisini yalnız anonim toplamlarla kullanır; personel adı, tanı, hekim notu, kısıtlama veya klinik durum döndürmez.
- Liste, özet, detay, Denetim Günü ve dosya yanıtlarında `Cache-Control: no-store` kullanılır.
- Başka tenant'a ait doğrudan kayıt kimliği istekleri, kaydın varlığını açığa çıkarmadan `404` döner.
- Bağlı `DocumentRecord`, `Company`, `IsgProfessional` ve `WorkplaceAssignment` kimlikleri OSGB/firma kapsamıyla çapraz doğrulanır.
- Soft deactivate kullanılır; firma/belge kayıtları API'den kalıcı silinmez.
- Excel'de `=`, `+`, `-`, `@` ile başlayan kullanıcı metni formül olmasın diye tek tırnakla etkisizleştirilir.
- PDF'de kullanıcı metni HTML olarak kaçışlanır.
- Denetim ZIP manifesti `external_submission_performed=false` içerir.
- Tenantlar arası OSGB karşılaştırma ucu yalnız `global_admin` rolüne açıktır ve yalnız toplulaştırılmış değer döndürür.

## 6. API ve arayüz

Ana API kökü: `/api/v1/authorized-firms`.

Profil listeleme/CRUD, dashboard, belge CRUD, profesyonel uygunluk upsert, onboarding, skor snapshot, PDF/XLSX, durum raporu, ZIP denetim paketi ve Denetim Günü uçları eklenmiştir.

Frontend'de OSGB yönetici menüsüne **Yetkili Firma Yönetimi** eklenmiş; OSGB ana paneline özet kartı ve İşyeri 360 görünümüne firma kartı bağlanmıştır. Bildirimler ilgili kayıttan bu modüle yönlenir.

## 7. Doğrulama kaydı

Geliştirme sırasında doğrulanan kapılar:

- Tam backend paketi: **918 geçti, 8 beklenen test atlandı, 0 hata**. Yeni kabul testleri tenant izolasyonu, company-bound admin engeli, ters tarihler, 30/60/90 uyarıları, profesyonel statüsü, görünür skor/geçmiş, mahremiyet, sözleşme dönemi, legacy uyumu, PDF/XLSX/ZIP güvenliği ve onboarding kapsamlarını doğrular.
- 0103 → 0104 izole SQLite migration smoke testi: başarılı, `0104_authorized_firm_compliance (head)`.
- Tüm migration zincirinin boş SQLite testi, bu değişiklikten önceki `0076_committee_professional_hardening` revizyonunun SQLite `ALTER CONSTRAINT` kısıtında durur. PostgreSQL üretim kapısı ayrıca çalıştırılmalıdır.
- Frontend: **29 test dosyası / 122 test geçti**; yeni modülün 5 saf mantık testi 30/60/90 tonları, filtre kodlama, payload normalizasyonu, tarih aralığı ve onboarding'i kapsar.
- ESLint: yeni modül dosyalarında 0 hata/uyarı; tam proje lint kapısı 0 hata ile geçti ve yalnız mevcut personel JSX uyarılarını raporladı.
- Vite production build: başarılı. Çalışma ortamı Node 24 kullanırken proje Node 20 ister; CI/production Node 20 ile yeniden çalıştırılmalıdır.
- Python bağımlılık taraması (`pip-audit -r requirements.txt`): **bilinen açık bulunmadı**. `pip check`: kırık bağımlılık yok.
- Frontend üretim bağımlılığı taraması (`npm audit --omit=dev --audit-level=high`): **0 açık**.
- Python modül derleme kontrolü (`compileall`): başarılı.

## 8. Yayın kararı

Bu dal doğrudan production'a alınmamalıdır. Önce:

1. PostgreSQL üzerinde `alembic upgrade head` ve RLS rol testleri,
2. Node 20 ile frontend test/lint/build,
3. bağımlılık yükseltmelerinin staging smoke testi,
4. staging güvenlik başlıkları ve dosya indirme doğrulaması,
5. staging rol/tenant ve çıktı smoke testleri,
6. yedek/rollback tatbikatı

tamamlanmalı; ardından PR review ve kontrollü deploy yapılmalıdır.
