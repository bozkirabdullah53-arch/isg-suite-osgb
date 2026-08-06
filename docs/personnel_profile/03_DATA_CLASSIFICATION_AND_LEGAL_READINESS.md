# Dijital Personel Kartı — Veri Sınıflandırma ve Hukuki Hazırlık Kapısı

> Bu belge hukuki görüş değildir. Teknik geliştirme ve production aktivasyonu öncesinde hangi kararların yetkili hukuk/organizasyon birimlerince verilmesi gerektiğini gösterir.

## 1. Durum kodları

- **GREEN:** sıradan profesyonel veri; yine de amaç, kapsam ve yetki uygulanır.
- **AMBER:** hassas/kurumsal gizli; ek yetki, saklama ve paylaşım kuralı gerekir.
- **RED:** özel nitelikli veya ağır kısıtlı; varsayılan kapalı, ayrı hukuki/organizasyonel readiness gerekir.
- **BLOCKED:** purpose/legal basis/retention/role tanımlı değil; geliştirme veya production işlemi yapılmaz.

## 2. Genel profil alanları

| Alan | Sınıf | Varsayılan görünürlük | CV | Dış paylaşım | Hazırlık durumu |
|---|---|---|---|---|---|
| Ad soyad | GREEN | Yetkili kapsam | Seçilebilir | Seçilebilir | Teknik olarak uygun |
| Personel/profil numarası | GREEN | Yetkili kapsam | Opsiyonel | Opsiyonel | Teknik olarak uygun |
| Meslek / ana görev | GREEN | Yetkili kapsam | Seçilebilir | Seçilebilir | Teknik olarak uygun |
| Departman | GREEN | Yetkili kapsam | Opsiyonel | Opsiyonel | Teknik olarak uygun |
| Şirket / işyeri | AMBER | Kapsam kontrollü | Özet | Özet | Müşteri gizliliği kuralı gerekli |
| Kurumsal e-posta | AMBER | Yetkili kapsam | Açık seçim | Açık seçim | Paylaşım amacı/izin kuralı gerekli |
| Telefon | AMBER | Yetkili kapsam | Açık seçim | Açık seçim | Paylaşım amacı/izin kuralı gerekli |
| Ev adresi | RED | Normal karta dahil değil | Hayır | Hayır | Varsayılan kapalı |
| Acil kişi/telefon | RED | Sınırlı İK/acil amaç | Hayır | Hayır | Hukuki/organizasyonel review gerekli |
| Tam doğum tarihi | AMBER | Minimum gerekli roller | Varsayılan hayır | Varsayılan hayır | Amaç ve minimizasyon kararı gerekli |
| TCKN | RED | Varsayılan maskeli | Hayır | Hayır | Ayrı güvenlik ve retention kararı gerekli |
| Maaş | RED | Personel kartı kapsam dışı | Hayır | Hayır | Kapsam dışı |
| Disiplin bilgisi | RED | Personel kartı kapsam dışı | Hayır | Hayır | Kapsam dışı |

## 3. Mesleki veri ve belgeler

| Kategori | Sınıf | Normal kart | CV | Dış paket | Saklama kararı |
|---|---|---|---|---|---|
| Diploma / mezuniyet | AMBER | Yetkili | Seçilebilir | Açık seçim | Organizasyon belirlemeli |
| İSG Uzmanı belgesi | AMBER | Yetkili | Seçilebilir | Açık seçim | Mesleki/yasal ihtiyaç değerlendirmesi |
| İşyeri Hekimi belgesi | AMBER | Yetkili | Seçilebilir | Açık seçim | Mesleki/yasal ihtiyaç değerlendirmesi |
| DSP belgesi | AMBER | Yetkili | Seçilebilir | Açık seçim | Mesleki/yasal ihtiyaç değerlendirmesi |
| Eğitici belgesi | AMBER | Yetkili | Seçilebilir | Açık seçim | Organizasyon belirlemeli |
| MYK / operatör / ustalık | AMBER | Yetkili | Seçilebilir | Açık seçim | Organizasyon belirlemeli |
| İlk yardımcı belgesi | AMBER | Yetkili | Seçilebilir | Açık seçim | Organizasyon belirlemeli |
| Proje/deneyim özeti | AMBER | Yetkili | Seçilebilir | Özet | Müşteri gizliliği kuralı gerekli |
| Tam müşteri dokümanı | RED | Normal karta dahil değil | Hayır | Hayır | Ayrı doküman yetkisi gerekir |

## 4. Sağlık verisi

### Normal kartta izin verilebilecek minimum durum

Yalnız hukuken gerekli ve organizasyonca onaylı ise:

- İşe uygun
- Kısıtla uygun
- Yeniden değerlendirme gerekli
- Muayene süresi dolmuş

### Normal kartta yasaklanan ayrıntılar

- teşhis
- ilaç
- laboratuvar sonucu
- görüntüleme
- gebelik bilgisi
- psikiyatrik bilgi
- engellilik teşhisi
- ayrıntılı hekim notu
- tıbbi rapor gövdesi

| İşlem | Durum |
|---|---|
| Sağlık ayrıntısını genel profil API’sinde döndürme | BLOCKED |
| Sağlık belgesini normal belge listesine ekleme | BLOCKED |
| Sağlık ayrıntısını CV’ye ekleme | BLOCKED |
| Sağlık ayrıntısını müşteri paketine ekleme | BLOCKED |
| Minimum uygunluk durumunu gösterme | Hukuki/rol/amaç onayı sonrası AMBER |

## 5. Adli sicil ve mahkûmiyet bilgisi

Adli sicil belgesi sıradan bir “eksik personel evrakı” değildir.

Aşağıdaki bilgiler yazılı olarak tanımlanmadan upload alanı açılmaz:

- belirli işleme amacı
- geçerli hukuki işleme şartı
- zorunluluk ve ölçülülük değerlendirmesi
- yetkili roller
- saklama süresi
- imha yöntemi
- paylaşım yasağı/istisnası
- erişim ve indirme audit seviyesi

| İşlem | Durum |
|---|---|
| Rutin olarak adli sicil isteme | BLOCKED |
| Eksik belge göstergesi yapma | BLOCKED |
| Normal sertifika listesinde gösterme | BLOCKED |
| CV’ye ekleme | BLOCKED |
| Müşteri paketine otomatik ekleme | BLOCKED |
| Hukuken doğrulanmış özel süreç | Ayrı RED mimari ve açık readiness sonrası değerlendirilebilir |

## 6. Mevcut `special_status` riski

Mevcut personel modeli ve Excel şablonu “Engelli/Hükümlü Durumu” bilgisini `special_status` alanında tutabilmektedir.

Geçici güvenli karar:

- Yeni profil özetinde varsayılan olarak gösterilmez.
- CV’ye dahil edilmez.
- dış paylaşım paketine dahil edilmez.
- arama ve filtreye eklenmez.
- yeni restricted belge yüklemesiyle ilişkilendirilmez.

Gerekli ayrı çalışma:

1. Production veri envanteri (yalnız sayı ve sınıflandırma; içerik sızdırmadan)
2. Gerçek işleme amaçlarının belirlenmesi
3. Yetki ve retention kararı
4. Gerekirse güvenli ayrıştırma/migrasyon planı
5. Mevcut Excel sözleşmesini bozmayan geçiş

## 7. Mevcut `national_id_masked` riski

Alan adı maskeli olmasına rağmen mevcut şablon tam 11 haneli değer kabul edebilir.

Yeni modül kuralları:

- API varsayılan yanıtı maskeli olmalı.
- CV ve dış paket tam değeri içermemeli.
- Object key, log, hata mesajı ve dosya adında bulunmamalı.
- Tam değere erişim ayrı backend yetkisi, amaç ve audit gerektirir.
- Mevcut veriyi otomatik dönüştürme Faz 2 kapsamına alınmaz.

## 8. Paylaşım readiness checklist

Dış paylaşım açılmadan önce her paket için zorunlu alanlar:

- [ ] Alıcı kişi tanımlı
- [ ] Alıcı kuruluş tanımlı
- [ ] Amaç tanımlı
- [ ] Hukuki aktarım şartı kayıtlı
- [ ] Seçili profil alanları açıkça listelenmiş
- [ ] Seçili belgeler açıkça listelenmiş
- [ ] Restricted veri seçili değil
- [ ] Süre makul ve son kullanma tarihi var
- [ ] Yetkilendiren kullanıcı kayıtlı
- [ ] Personel bildirim/onay kuralı uygulanmış
- [ ] Kalıcı public URL üretilmiyor
- [ ] Erişim ve indirme auditleniyor
- [ ] İptal mekanizması var

Eksik madde varsa paylaşım işlemi backend tarafından reddedilir.

## 9. Retention readiness şablonu

Her belge kategorisi için aşağıdaki kayıt tamamlanmadan production aktivasyonu yapılmaz:

| Alan | Zorunlu açıklama |
|---|---|
| Kategori | Belge/veri adı |
| İşleme amacı | Belirli ve meşru amaç |
| Hukuki şart | Yetkili hukuk değerlendirmesi |
| Zorunlu/opsiyonel | Profil tamlığına etkisi |
| Yetkili roller | Görme/yükleme/doğrulama/indirme ayrı ayrı |
| Alıcılar | İç/dış alıcı grupları |
| Aktif saklama | Süre veya olay |
| Arşiv | Süre veya olay |
| İmha | Silme/yok etme/anonimleştirme |
| Yasal blok | İmha engeli ve süresi |
| Türetilmiş dosyalar | CV/paylaşım paketi/önizleme temizliği |
| Audit | Gerekli olaylar |

## 10. Production readiness durumları

### Genel profil özeti

- Teknik tasarım: **hazırlanabilir**
- Production aktivasyonu: feature flag + tenant testleri sonrası pilot

### Fotoğraf ve normal mesleki belgeler

- Teknik tasarım: **hazırlanabilir**
- Production aktivasyonu: private R2 durability + kategori retention kararı sonrası

### PDF CV

- Teknik tasarım: **hazırlanabilir**
- Production aktivasyonu: alan önizlemesi + restricted dışlama + paylaşım politikası sonrası

### Dış paylaşım

- Teknik tasarım: **ayrı feature flag altında hazırlanabilir**
- Production aktivasyonu: amaç/aktarim şartı/alıcı/süre matrisi tamamlanmadan **BLOCKED**

### Sağlık ayrıntısı

- Normal personel kartı: **BLOCKED**
- Mevcut sağlık modülünde ayrı erişim: korunur

### Adli sicil

- Production geliştirmesi/aktivasyonu: hukuki ve organizasyonel assessment tamamlanmadan **BLOCKED**

## 11. Onay kayıtları

Bu dokümandaki “hazır” durumu otomatik veya evrensel hukuki uyumluluk iddiası değildir.

Production açılışından önce organizasyon tarafından kayıt altına alınması gereken onaylar:

- [ ] Veri işleme envanteri sahibi
- [ ] Hukuk/KVKK değerlendirmesi
- [ ] Bilgi güvenliği değerlendirmesi
- [ ] İK/OSGB operasyon sahibi
- [ ] Rol ve erişim matrisi sahibi
- [ ] Saklama ve imha politikası sahibi
- [ ] R2/veri işleyen hizmet sağlayıcı değerlendirmesi
- [ ] İhlal müdahale süreci
- [ ] Veri sahibi başvuru süreci
- [ ] Pilot kullanıcı kabulü
