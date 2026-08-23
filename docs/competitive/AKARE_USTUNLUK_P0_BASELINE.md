# İSG Suite — aKareİSG Üstünlük Programı / P0 Baseline

**Durum:** P0 çalışan self-servis canary hazırlığında
**Çalışma dalı:** `codex/akare-ustunluk-p0-employee-self-service-20260824`
**Hedef:** aKareİSG'nin hazır ticari ürün ve mobil olgunluk seviyesini **geçmek**.  
**Kapsam:** İBYS ve MEDULA/e-Reçete dışındaki fonksiyonlar. Bu iki konu bu programda ölçülmez, geliştirilmez ve puanlanmaz.

Bu belge yalnızca güvenli çalışma sözleşmesidir. Runtime koduna, mevcut API'lere,
veritabanı verilerine veya canlı ortama etkisi yoktur.

## 1. Değişmez no-break protokolü

- `master` dalındaki çalışan akışlar korunur; doğrudan `master` üzerinde geliştirme yapılmaz.
- Mevcut route, endpoint, tablo, kolon, rol ve veri formatı silinmez veya yeniden adlandırılmaz.
- Yeni davranışlar feature flag arkasında ve varsayılan olarak kapalı başlar.
- Migration yaklaşımı expand/validate/rollout şeklindedir; ilk aşamada destructive migration yoktur.
- Eski kayıtlar geriye dönük yeniden yazılmaz.
- Her değişiklik küçük, geri alınabilir bir commit ve ayrı PR olarak hazırlanır.
- Canlıya almadan önce veritabanı yedeği, restore provası ve kill-switch doğrulaması yapılır.
- Eski akışlar flag kapalıyken; yeni akışlar flag açıkken ayrı ayrı test edilir.
- Kritik regresyon, tenant izolasyonu veya veri kaybı riski varsa yayın yapılmaz.

## 2. Mevcut baseline gözlemleri

- Repository README'si risk, ramak kala, iş kazası, DÖF, eğitim, sağlık, doküman,
  raporlama, OSGB, PWA ve mobil uyumlu arayüz bileşenlerini listeliyor.
- CI; backend SQLite smoke, PostgreSQL migration/parity, frontend test/lint/build,
  Playwright E2E ve npm audit kapılarını içeriyor.
- Canlı UI QA kaydında mobil responsive piksel testi ve tüm rollerin menü matrisi
  kapsam dışında bırakılmış.
- Son commit'lerde mobil saha kabuğu, kamera, viewport taşması ve offline kuyruğu
  üzerinde ardışık düzeltmeler yapılmış. Yeni iş bu mevcut saha akışının yerine
  geçmeyecek; onun üzerine izole edilecek.

## 3. P0 teslimatları

### P0-01 — Altın akış envanteri

Aşağıdaki akışların mevcut davranışı, route'u, API çağrısı, veri modeli, rolü ve
testi kayıt altına alınacak:

1. Saha gözlemi/tespit oluşturma
2. Risk analizi ve risk skorunun kaydı
3. Riskten DÖF oluşturma, kanıt ekleme ve kapatma
4. Ramak kala/olay kaydı ve inceleme
5. Eğitim atama, ilerleme, sınav ve sertifika
6. KKD stok, zimmet, teslim ve iade
7. Sağlık kaydı ve periyodik takip
8. Doküman, acil durum, tatbikat ve kurul aksiyonu
9. OSGB/firma/şube/kullanıcı yetki izolasyonu
10. Mobil/PWA açılış, bağlantı kopması ve tekrar senkronizasyon

**Kabul:** Her akış için mevcut route/API, yetki, veri tablosu, test komutu ve
beklenen sonuç yazılı olacak; eksik bilgi varsayımla kapatılmayacak.

### P0-02 — Regresyon kapısı

Mevcut CI kapılarına ek olarak aşağıdakiler tamamlanacak:

- Her altın akış için flag kapalı legacy testi
- Firma/tenant çapraz erişim negatif testi
- Rol bazlı menü ve endpoint testi
- Mobil 390x844, 430x932 ve tablet görünüm smoke testi
- Offline kayıt, yeniden deneme ve çift gönderim/idempotency testi
- Eski PDF/Excel ve sertifika akışlarının geriye dönük kontrolü

### P0-03 — Rollback provası

- Çalışma dalı ve release SHA kaydı
- Veritabanı yedekleme/restore adımı
- Feature flag kapatma
- Migration doğrulama
- Hatalı rollout sonrası eski davranışa dönüş

**Kabul:** Uygulama verisi kaybolmadan, yeni özellik kapatılarak eski akışın
çalıştığı kanıtlanacak.

## 4. Tamamlanan izolasyonlu başlangıç

İlk kod sprinti, mevcut saha modülünü değiştirmeden şu kapsamda tamamlandı:

**Mobil saha güvenilirlik katmanı**

- Yeni bir mobil sync durum göstergesi
- Taslak/kuyruk/başarılı/hata durumları
- İdempotent tekrar gönderim
- Bağlantı geri geldiğinde kontrollü retry
- Kullanıcıya veri kaybı olmadığını gösteren kayıt özeti
- Mevcut `field_offline` ve `field_inspection_offline` davranışını koruyan adapter

Bu sprintte mevcut endpoint sözleşmesi değiştirilmeyecek; yeni katman mevcut
API'ye adapter üzerinden bağlanacaktır.

Uygulanan temel güvenilirlik katmanı:

- `VITE_MOBILE_SYNC_STATUS_V1` varsayılan olarak kapalıdır.
- Mevcut offline kuyruklarını değiştirmeden görünür senkron durumunu gösterir.
- Unit testi ve flag-kapalı geriye dönük davranış kontrolü vardır.

## 5. Mevcut güvenli teslimat — çalışan self-servis P0

Bir sonraki üstünlük adımı olarak `employee_self_service_enabled` ve
`VITE_EMPLOYEE_SELF_SERVICE_V1` arkasında salt okunur **Çalışan Panelim**
eklenmiştir. Bu aşamada iki bayrak da kapalıdır.

- Hesap → çalışan ilişkisi yalnızca mevcut açık eşleştirme kaydından okunur;
  ad-soyad tahmini yapılmaz.
- Çalışan yalnız kendi firması ve kendi çalışan kaydı için eğitim, KKD,
  bildirim ve sağlık takvimi özetini görür.
- Sağlık yanıtı yalnız muayene tarihlerini içerir; klinik sonuç, tanı,
  kısıt, rapor ve notlar dışarıda bırakılır ve erişim audit zincirine yazılır.
- Endpoint yazma/yükleme işlemi sunmaz; mevcut role, global yönetici menüsüne
  veya OSGB saha menülerine ek yetki vermez.
- Yeni tablo veya migration yoktur; mevcut kayıtlar geriye dönük yazılmaz.

Canary kabulü: aynı rol/tenant negatif testleri, flag kapalı smoke, 390x844 ve
430x932 gerçek cihaz smoke, sağlık veri minimizasyonu ve rollback/force-off
kontrolü geçmeden bayraklar açılmayacaktır.

## 6. aKareİSG'yi geçtiğimizi gösteren zorunlu ölçüt

Program başarılı sayılmayacak; şu şartların tamamı aranacak:

- Kritik non-İBYS/non-MEDULA akışlarının tamamı mobilde tamamlanabilmeli.
- Hiçbir kritik akışta aKareİSG'den geride kalınmamalı.
- En az üç ölçülebilir üstünlük kanıtlanmalı:
  - internetsiz saha çalışması,
  - daha güvenilir senkronizasyon,
  - daha kısa işlem akışı,
  - daha güçlü kanıt/denetim izi,
  - daha iyi firma/rol görünürlüğü.
- Gerçek cihaz ve gerçek rol matrisi testi tamamlanmalı.
- Yeni özellik kapalıyken mevcut uygulama davranışı değişmemeli.
- Kritik regresyon, veri kaybı veya tenant izolasyonu açığı bulunmamalı.

## 7. Yasaklar

Bu program kapsamında:

- Çalışan modül yeniden yazılmayacak.
- Büyük çaplı frontend/backend rewrite yapılmayacak.
- Canlı veriye doğrudan düzeltme uygulanmayacak.
- Eski kayıtlar silinmeyecek.
- İBYS veya MEDULA/e-Reçete geliştirmesi yapılmayacak.
- Test geçmeden feature flag açılmayacak.

**Sıradaki hedef:** Çalışan Panelim'i staging/canary'de gerçek bir salt okunur
çalışan hesabıyla doğrulamak; ardından KKD, eğitim, bildirim ve mobil offline
kanıt akışlarında ikinci üstünlük paketine geçmektir.
