# İBYS Entegratör Başvuru Dosyası Kontrol Listesi

Durum kodları:

- `HAZIR`: Dosya üretilebilir ve teknik kanıtı mevcut.
- `DOĞRULAMA`: İçerik hazır; CI/staging veya yetkili imza doğrulaması bekliyor.
- `KURUMDAN`: Başvuru sahibi şirket/yetkiliden alınması gereken belge.
- `BAKANLIKTAN`: İSGGM tarafından sağlanacak resmî sözleşme veya bilgi.
- `RANDEVUDA`: İlk görüşmede teyit edilecek husus.

## A. Başvuru sahibi kurumsal evrakları

| No | Belge | Durum | Sorumlu | Kabul ölçütü |
|---|---|---|---|---|
| A-01 | Başvuru dilekçesi | DOĞRULAMA | Yetkili temsilci | Ticari unvan, vergi no, MERSİS, iletişim, yazılım adı ve başvuru talebi eksiksiz; ıslak/e-imzaya hazır |
| A-02 | Güncel ticaret sicil gazetesi | KURUMDAN | Şirket | Güncel ortaklık ve temsil bilgileri görünür |
| A-03 | Faaliyet belgesi / oda kayıt belgesi | KURUMDAN | Şirket | Güncel tarihli |
| A-04 | Vergi levhası | KURUMDAN | Şirket | Ticari unvan ve vergi no başvuru formuyla uyumlu |
| A-05 | İmza sirküleri / imza beyannamesi | KURUMDAN | Yetkili temsilci | Başvuruyu imzalayan kişinin yetkisi doğrulanmış |
| A-06 | Yetkili kişi kimlik ve iletişim bilgileri | KURUMDAN | Yetkili temsilci | KVKK’ya uygun kapalı ek olarak sunulur |
| A-07 | Yazılım sahipliği / lisans hakkı beyanı | DOĞRULAMA | Şirket + hukuk | Kaynak kod, marka ve kullanım hakları açıklanmış |
| A-08 | Teknik irtibat kişisi görevlendirme yazısı | KURUMDAN | Şirket | Ad, unvan, e-posta ve telefon teyitli |

## B. Yazılım ve mimari dosyaları

| No | Belge / kanıt | Durum | Kanıt |
|---|---|---|---|
| B-01 | Ürün tanıtım ve kapsam dokümanı | HAZIR | İSG Suite OSGB modül envanteri |
| B-02 | Sistem mimarisi | HAZIR | FastAPI, PostgreSQL, React, Redis, Render servis topolojisi |
| B-03 | Tenant izolasyonu tasarımı | HAZIR | 47 tablo RLS + FORCE RLS ve gerçek tenant davranış testi |
| B-04 | Yetkilendirme matrisi | HAZIR | Global admin, OSGB admin, uzman, hekim, DSP ve işyeri rolleri |
| B-05 | API sürümleme ve hata modeli | DOĞRULAMA | Aday İBYS profil API’si ve standart doğrulama raporu |
| B-06 | Veri-seti eşleme matrisi | DOĞRULAMA | 12 aday veri seti; resmî kod/alanlar Bakanlık sözleşmesini bekliyor |
| B-07 | İdempotency ve mükerrer gönderim tasarımı | DOĞRULAMA | Deterministik kayıt fingerprint’i ve zarf idempotency anahtarı |
| B-08 | Kayıt bazlı kabul/ret raporu | DOĞRULAMA | Eksik alan listesi + kayıt fingerprint’i; hassas içerik rapora yazılmaz |
| B-09 | Audit log ve izlenebilirlik | HAZIR | Kullanıcı, zaman, OSGB kapsamı ve entegrasyon işlem kayıtları |
| B-10 | Yedekleme ve bütünlük | HAZIR | 66/66 checksum; SHA-256 ve ZIP güvenlik preflight |
| B-11 | Felaket kurtarma ve restore tatbikat raporu | DOĞRULAMA | Gerçek staging geri dönüş tatbikatı ayrıca tamamlanacak |

## C. Bilgi güvenliği ve KVKK ekleri

| No | Belge / kanıt | Durum | Kabul ölçütü |
|---|---|---|---|
| C-01 | KVKK veri envanteri | DOĞRULAMA | Veri kategorisi, amaç, hukuki sebep, saklama süresi, alıcı grubu |
| C-02 | Özel nitelikli sağlık verisi güvenliği | HAZIR | Dedicated şifreleme anahtarı, role dayalı erişim, counts-only envanter |
| C-03 | Aktarım güvenliği | HAZIR | TLS, secret loglamama, timeout, fail-closed yapılandırma kapıları |
| C-04 | Parola ve oturum güvenliği | HAZIR | Güçlü secret, JWT/refresh, pasif kullanıcı engeli, MFA altyapısı |
| C-05 | Dosya yükleme güvenliği | DOĞRULAMA | İmza/MIME kontrolleri; gerçek ClamAV servisi henüz etkin değil |
| C-06 | Zafiyet ve penetrasyon testi | DOĞRULAMA | CI audit mevcut; bağımsız pentest/ZAP raporu ayrıca hazırlanacak |
| C-07 | Olay müdahale prosedürü | DOĞRULAMA | Sınıflandırma, bildirim, izolasyon, kanıt saklama ve kapanış adımları |
| C-08 | Saklama ve imha politikası | DOĞRULAMA | Veri türü bazlı süre ve doğrulanabilir imha kayıtları |

## D. Test ve demo dosyaları

| No | Test / kanıt | Durum | Kabul ölçütü |
|---|---|---|---|
| D-01 | Birleşik backend testleri | HAZIR | SQLite ve PostgreSQL test paketleri başarılı |
| D-02 | Migration ve şema parity | HAZIR | Alembic head ve PostgreSQL parity başarılı |
| D-03 | Frontend test/lint/build/E2E | HAZIR | GitHub Actions başarılı |
| D-04 | İBYS aday profil testleri | DOĞRULAMA | 12 veri seti, zorunlu alan, fingerprint, idempotency testleri |
| D-05 | Geçerli kayıt demo senaryosu | HAZIR | Kabul sayısı ve deterministik fingerprint |
| D-06 | Eksik zorunlu alan senaryosu | HAZIR | Kayıt bazlı ret ve eksik alan listesi |
| D-07 | Mükerrer gönderim senaryosu | HAZIR | Aynı kayıt kümesinde aynı idempotency anahtarı |
| D-08 | Tenant dışı erişim senaryosu | HAZIR | RLS ve API kapsam kontrolü ile engelleme |
| D-09 | Resmî endpoint bağlantı testi | BAKANLIKTAN | Test URL, sertifika/anahtar ve ağ izinleri gerekli |
| D-10 | Bakanlık kabul/ret kodları testi | BAKANLIKTAN | Resmî hata kataloğu gerekli |

## E. Bakanlıktan talep edilecek teknik bilgiler

| No | Bilgi / belge | Durum |
|---|---|---|
| E-01 | Güncel veri-seti kataloğu ve sürüm numarası | BAKANLIKTAN |
| E-02 | Her veri setinin alan adı, türü, zorunluluk ve kod listeleri | BAKANLIKTAN |
| E-03 | Test ve production endpoint listesi | BAKANLIKTAN |
| E-04 | Kimlik doğrulama / sertifika / imza yöntemi | BAKANLIKTAN |
| E-05 | İstek ve yanıt örnekleri | BAKANLIKTAN |
| E-06 | Hata ve ret kodları | BAKANLIKTAN |
| E-07 | Idempotency / mükerrer kayıt kuralı | BAKANLIKTAN |
| E-08 | Gönderim sıklığı, toplu kayıt limiti ve zaman aşımı | BAKANLIKTAN |
| E-09 | Kişisel veri maskeleme ve loglama kısıtları | BAKANLIKTAN |
| E-10 | Kabul testi senaryoları ve tescil kapanış kriterleri | BAKANLIKTAN |

## F. Başvuru kapanış kapıları

Başvuru randevusu alınmadan önce aşağıdaki beş şart birlikte sağlanmalıdır:

1. A grubu kurumsal belgeler yetkili temsilci tarafından teslim edilmiş olmalı.
2. B–D teknik ekleri tek sürümlü ZIP/PDF dosyası olarak üretilebilmeli.
3. Aday İBYS profil API’si CI ve staging’de başarılı olmalı.
4. Bakanlığa gönderilecek randevu talep yazısı ve soru listesi onaylanmış olmalı.
5. Sunumda “resmî uygunluk” değil, “tescil başvurusu ve resmî sözleşme talebi” ifadesi kullanılmalı.
