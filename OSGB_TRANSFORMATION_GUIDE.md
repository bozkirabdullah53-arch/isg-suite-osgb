# İSG Suite v0.8 — OSGB Dönüşümü

Bu sürüm, `Company` kaydını hizmet verilen müşteri işyeri olarak konumlandırır ve üst katmana bağımsız bir `OsgbOrganization` ekler.

## Eklenen çekirdek yapı

- OSGB kuruluşları
- İSG profesyonelleri
- İş güvenliği uzmanı / işyeri hekimi / DSP türleri
- Profesyonel–işyeri görevlendirmeleri
- Aylık zorunlu, planlanan ve gerçekleşen süreler
- İSG-KATİP sözleşme numarası
- OSGB–müşteri işyeri hizmet sözleşmeleri
- Kullanıcı ve işyerlerinde `osgb_id` veri izolasyonu temeli

## Yeni API uçları

- `GET/POST /api/v1/osgb`
- `GET/POST /api/v1/osgb/professionals`
- `GET/POST /api/v1/osgb/assignments`
- `GET/POST /api/v1/osgb/contracts`

## Sonraki zorunlu aşamalar

1. OSGB yönetim ekranları
2. Profesyonel takvimi ve saha ziyaretleri
3. İşyerine hizmet durumu matrisi
4. Sözleşme, CRM, teklif, cari ve tahsilat
5. Mevzuat veri seti ve NACE kuralları
6. İBYS/İSBS entegrasyonları için yetkili servis sözleşmeleri
7. KVKK, penetrasyon testi ve dosya antivirüs taraması
