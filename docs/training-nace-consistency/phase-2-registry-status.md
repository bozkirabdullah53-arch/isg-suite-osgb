# Faz 2 — Sürümlü NACE Registry Durum Raporu

**Tarih:** 5 Ağustos 2026  
**Durum:** Devam ediyor — Faz 3'e geçiş kapısı henüz kapalıdır.  
**CI:** #493 / run `31002142423` — başarılı  
**Doğrulanan head:** `729f93d63a991c6bd2751cf30c429ec40cb74ab2`

## Kanıt zinciri

- Registry schema: `nace-training-registry-v1`
- Registry content SHA-256: `0a930516590635d623f511259c64098e420a35c3ff0354291b703f66964cf00f`
- GitHub artifact: `nace-registry-evidence`
- Artifact ID: `8928726544`
- Artifact digest: `sha256:99580479031b7a11b8016601195c090858ac8550079e6686c5f03a44989a49c0`
- Saklama süresi: 90 gün

## Katalog kapsamı

- Toplam NACE kaydı: **2.141**
- Benzersiz altılı NACE: **2.141**
- `mapped`: **662**
- `review_required`: **1.479**
- `blocked`: **0**
- Otomatik tümü uyumlu sonucu: **false**

## Tehlike sınıfı dağılımı

- Az Tehlikeli: **897**
- Tehlikeli: **888**
- Çok Tehlikeli: **356**

## Review-required kök nedenleri

- Açık risk etiketi henüz tanımlanmamış profil kayıtları: **1.046**
- Risk etiketi olsa dahi aşırı geniş kabul edilen `depo_lojistik`, `ofis` ve `tarim` profilleri: **433**

## En büyük inceleme grupları

| Profil | Kayıt |
|---|---:|
| depo_lojistik | 256 |
| perakende | 145 |
| ofis | 124 |
| bakım-onarım/teknik servis | 81 |
| genel üretim | 55 |
| metal işleme/torna-freze | 54 |
| tarım | 53 |
| elektronik | 48 |
| demir-çelik/hadde | 44 |
| inşaat | 36 |
| eğitim kurumu | 34 |
| belediye/kamu hizmetleri | 33 |
| sağlık/hastane/klinik | 33 |
| banka/finans | 31 |

## Uygulanan güvenlik kuralları

1. Kesin altılı NACE kodu birincil kimliktir.
2. Geniş legacy profil anahtarından kesin NACE kodu tahmin edilmez.
3. Katalog sürümü içerik hash'iyle değişmez hâle getirilir.
4. Yeni sürüm yalnız `candidate` olarak oluşturulur; kendiliğinden aktive edilmez.
5. Eksik profil veya risk eşlemesi “uyumlu” sayılmaz.
6. 8/12/16 ders saati ile öğretim dakikası ve mola dâhil takvim dakikası ayrı tutulur.
7. Faz 2 kayıtları mevcut eğitim/sınav/sertifika davranışını değiştirmez.

## CI doğrulamaları

- SQLite registry ve legacy audit testleri: başarılı
- Kesin NACE normalizasyonu: başarılı
- 2.141 kayıt ve benzersizlik: başarılı
- Akü `27.20.01` kesin profil/risk testi: başarılı
- Kuaför profilinde endüstriyel patlayıcı risk bulunmaması: başarılı
- Balıkçılık profilinde traktör/pestisit risk bulunmaması: başarılı
- Legacy `tarim` profilinden kesin NACE tahmini yapılmaması: başarılı
- Alembic `0078_training_nace_registry`: başarılı
- PostgreSQL şema eşitliği: başarılı
- PostgreSQL 2.141 satır materializasyonu: başarılı
- Materializasyon idempotency: başarılı
- Aktif katalog sürümünün kendiliğinden oluşmaması: başarılı
- Frontend test/lint/build/E2E/audit: başarılı

## Faz 2'yi kapatmak için kalanlar

1. Açık risk haritası bulunmayan 58 profil grubunu insan tarafından okunabilir, açık ve test edilebilir risk etiketleriyle tamamlamak.
2. Aşırı geniş profilleri ana sektör, alt sektör, NACE öneki ve faaliyet grubu katmanlarına ayırmak.
3. Her exact NACE için konu/risk eşleşmesinin soru havuzuna bağlanabilecek yeterlilikte olduğunu doğrulamak.
4. Yanlış profil eşleşmelerini kod bazında raporlamak ve düzeltmek.
5. Güncellenmiş registry artifact'inde `review_required` listesini gerçek inceleme sonucuna göre azaltmak.
6. Hiçbir kaydı yalnız metin benzerliğiyle eşlememek.

## Sonuç

Faz 2'nin altyapısı ve kanıt mekanizması başarıyla kurulmuştur; ancak sınıflandırma incelemesi tamamlanmamıştır. 1.479 kayıt çözülmeden veya açıkça bloke edilmeden Faz 3 soru bankası motoru devreye alınmayacaktır.
