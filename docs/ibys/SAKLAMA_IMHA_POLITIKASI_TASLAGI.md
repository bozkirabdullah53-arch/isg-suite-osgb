# İBYS Verileri Saklama ve İmha Politikası Taslağı

> Bu belge teknik uygulama taslağıdır. Kesin süreler veri sorumlusu, hukuk/KVKK sorumlusu ve güncel mevzuat değerlendirmesiyle onaylanmalıdır.

## İlkeler

1. Amaçla sınırlılık ve veri minimizasyonu
2. Mevzuat veya sözleşmede zorunlu süreden uzun saklamama
3. Tenant bazlı erişim ve imha kapsamı
4. Sağlık verilerinde özel nitelikli veri koruması
5. İmha işlemlerinin doğrulanabilir audit kaydı
6. Yedeklerde süre gecikmesi ve güvenli yaşam döngüsü
7. Hukuki uyuşmazlık/inceleme hâlinde kontrollü saklama dondurması

## Veri sınıfları ve teknik yaşam döngüsü

| Veri sınıfı | Aktif kullanım | Arşiv | İmha yöntemi | Onay gereken süre |
|---|---|---|---|---|
| İşyeri ve OSGB kayıtları | Hizmet ilişkisi boyunca | Yasal/denetim gereğine göre | DB silme/anonimleştirme + dosya temizliği | Hukuk |
| Çalışan temel kayıtları | İstihdam/hizmet boyunca | Yasal yükümlülük boyunca | Kimlik alanlarını anonimleştirme veya silme | Hukuk/KVKK |
| Eğitim kayıtları | Operasyon ve denetim | Yasal kanıt süresi | DB ve ek dosya imhası | İSG mevzuat sorumlusu |
| Sağlık kayıtları | Yetkili sağlık personeli erişimi | Özel nitelikli veri süresi | Şifreli alan ve ek dosyaların güvenli imhası | Hekim + hukuk/KVKK |
| Kaza/meslek hastalığı | Süreç ve bildirim | Yasal/uyuşmazlık süresi | Kapsamlı imha/anonimleştirme | Hukuk |
| Risk, saha ve DÖF | Aktif işyeri takibi | Denetim kanıt süresi | DB ve dosya imhası | İSG sorumlusu |
| Entegrasyon işlem logları | Gönderim/mutabakat | Sözleşme ve güvenlik incelemesi | Metadata silme; içerik zaten tutulmaz | Teknik + hukuk |
| Güvenlik/audit logları | Olay tespiti | Sınırlı güvenlik süresi | Log yaşam döngüsüyle silme | Bilgi güvenliği |
| Tenant yedekleri | Felaket kurtarma | Belirlenen rotasyon süresi | Şifreli arşivi silme + kayıt durumunu audit etme | Sistem sahibi |

## Teknik imha kontrolleri

- İmha isteği tenant ve veri kategorisi kapsamında çalışır.
- Yetkisiz rol imha başlatamaz.
- Sağlık verisi imhası ek yetki/onay gerektirir.
- Object storage ve persistent disk kopyaları birlikte ele alınır.
- İlgili kayıt aktif yedeklerde kalıyorsa yedek rotasyon tarihi raporlanır.
- İmha audit kaydı içerik yerine kayıt kimliği/fingerprint, kullanıcı, zaman ve işlem sonucunu taşır.
- Silme öncesinde hukuki saklama dondurması kontrol edilir.

## Başvuru öncesi tamamlanacak alanlar

- Her veri sınıfının kesin saklama süresi
- Sürenin hukuki dayanağı
- Periyodik imha takvimi
- İmha onay rolleri
- Yedek rotasyon ve gecikmeli imha kuralı
- Veri sahibi talep prosedürü
- Hukuki saklama dondurması prosedürü
