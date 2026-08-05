# İBYS Entegratör Başvuru Hazırlık Dosyası

Bu klasör, İSG Suite OSGB yazılımının Çalışma ve Sosyal Güvenlik Bakanlığı İş Sağlığı ve Güvenliği Genel Müdürlüğüne yapılacak İBYS entegratör başvurusu için hazırlanmıştır.

## Kritik sınır

Bu dosya **Bakanlık tescili veya resmî İBYS teknik uygunluğu iddia etmez**. Bakanlığın güncel resmî veri seti, servis sözleşmesi, kimlik doğrulama yöntemi ve test ortamı erişimi henüz projeye teslim edilmemiştir.

Başvuru hazırlığı iki ayrı kapıdan oluşur:

1. **Başvuruya hazır kurumsal ve teknik dosya:** Yazılım mimarisi, veri güvenliği, tenant izolasyonu, test kanıtları, demo senaryoları ve sürümlü aday veri eşleme profili.
2. **Resmî teknik sözleşme uyarlaması:** İSGGM tarafından teslim edilen veri-seti kodları, alan adları, endpoint, kimlik doğrulama, hata kodları ve kabul senaryolarının sisteme işlenmesi.

## Dosya indeksi

- `BASVURU_DOSYASI_KONTROL_LISTESI.md`: Kurumsal, hukuki ve teknik evrakların sahiplik/durum listesi.
- `TEKNIK_UYGUNLUK_MATRISI.md`: Mevcut sistem kabiliyetleri ile başvuru kanıtlarının eşlemesi.
- `DEMO_KABUL_SENARYOLARI.md`: Bakanlık sunumu/test görüşmesi için kabul ve ret senaryoları.
- `RESMI_SOZLESME_TESLIM_TUTANAGI.md`: Resmî veri şeması ve servis sözleşmesi alındığında doldurulacak kontrol tutanağı.
- `application-manifest.json`: Makine tarafından okunabilir başvuru durumu ve kapanış kapıları.

## Teknik demo API'leri

Yalnız global yönetici ve OSGB yöneticisi rolleri erişebilir:

- `GET /api/v1/ibys-application/profile`
- `GET /api/v1/ibys-application/readiness`
- `POST /api/v1/ibys-application/validate/{dataset_code}`
- `POST /api/v1/ibys-application/envelope/{dataset_code}`

Bu uç noktalar harici İBYS çağrısı yapmaz. Aday kayıtları zorunlu alan, deterministik fingerprint ve idempotency açısından doğrular.

## Başvuruya hazır sayılma kuralı

Başvuru hazırlığı %100 sayılabilmesi için:

- Teknik aday profil ve demo kabul paketi CI + staging üzerinde doğrulanmış olmalı.
- Kurumsal evraklar yetkili kişi tarafından temin edilip kontrol edilmeli.
- Başvuru dilekçesi imzaya hazır olmalı.
- KVKK/veri güvenliği ve sistem mimarisi ekleri hazırlanmalı.
- İSGGM ile resmî veri sözleşmesi/test ortamı talep yazısı hazırlanmalı.
- Randevu talep iletişim metni ve sunum gündemi hazır olmalı.

Resmî İBYS uygunluğu ise ancak Bakanlık sözleşmesi ve kabul testleri tamamlandıktan sonra ayrıca ilan edilebilir.
