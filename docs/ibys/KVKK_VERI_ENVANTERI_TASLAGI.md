# İBYS Başvurusu KVKK Veri Envanteri Taslağı

> Bu teknik envanter, veri akışını ve güvenlik kontrollerini gösterir. Hukuki sebep, saklama süresi ve VERBİS ifadeleri başvuru sahibi veri sorumlusu/hukuk danışmanı tarafından doğrulanmalıdır.

| Veri kategorisi | Örnek alanlar | İlgili kişi | İşleme amacı | Teknik koruma | Alıcı / aktarım | Saklama-imha onayı |
|---|---|---|---|---|---|---|
| İşyeri kimlik bilgileri | SGK sicil no, vergi no, NACE, adres | İşveren/işyeri | İSG hizmet yönetimi ve resmî bildirim hazırlığı | Tenant scope, RLS, audit | Yetkili kullanıcı; tescil sonrası Bakanlık | Hukuk onayı gerekli |
| Çalışan kimlik bilgileri | Ad soyad, TCKN, işe giriş | Çalışan | İSG eğitim, sağlık ve görevlendirme süreçleri | RLS, rol kontrolü, loglarda maskeleme | Yetkili OSGB/işveren; resmî kurumlar | Hukuk onayı gerekli |
| İletişim bilgileri | Telefon, e-posta, adres | Çalışan/profesyonel/yetkili | Operasyon ve bildirim | Rol kontrolü, TLS | Yetkili kullanıcılar | Hukuk onayı gerekli |
| Mesleki bilgiler | Ünvan, bölüm, görev, sertifika | Çalışan/İSG profesyoneli | Yetkinlik ve görevlendirme | Tenant scope, audit | OSGB, işveren, İSGGM/İSG-KATİP süreçleri | Hukuk onayı gerekli |
| Eğitim kayıtları | Eğitim konusu, tarih, süre, eğitici | Çalışan | Mevzuat yükümlülüğü ve kanıt | RLS, değişiklik izi | Yetkili taraflar; tescil sonrası Bakanlık | Hukuk onayı gerekli |
| Sağlık verileri | Muayene, tetkik, uygunluk, tanı kodu | Çalışan | Sağlık gözetimi | Dedicated alan şifreleme, hekim/rol erişimi, counts-only envanter | Yetkili sağlık personeli; mevzuatın izin verdiği kurumlar | Özel nitelikli veri politikası gerekli |
| İş kazası/ramak kala | Olay zamanı, yaralanma, etkilenen kişi | Çalışan | Kaza araştırması ve yasal bildirim | RLS, audit, rol kontrolü | Yetkili kullanıcı ve resmî kurumlar | Hukuk onayı gerekli |
| Meslek hastalığı | Tanı kodu/tarihi, çalışan | Çalışan | Yasal bildirim ve sağlık takibi | Sağlık verisi şifreleme, sıkı rol | Yetkili hekim ve resmî kurumlar | Özel nitelikli veri politikası gerekli |
| Risk ve saha kayıtları | Tehlike, risk, fotoğraf, ziyaret, tespit | Çalışan/işyeri | Önleme, denetim ve düzeltici faaliyet | Tenant scope, dosya güvenliği, audit | Yetkili kullanıcılar | Hukuk onayı gerekli |
| Kullanıcı ve güvenlik logları | Kullanıcı id, IP, zaman, işlem | Sistem kullanıcısı | Güvenlik, denetim, hata araştırması | Erişim kısıtı, bütünlük, secret redaction | Yetkili sistem yöneticileri | Süre ve amaç sınırlaması gerekli |
| Entegrasyon logları | Adapter, kayıt sayısı, durum, HTTP kodu | Sistem kullanıcısı/işyeri | Gönderim izlenebilirliği | İçerik yerine metadata/fingerprint | Yetkili yönetici; gerektiğinde Bakanlık | Hukuk onayı gerekli |

## Veri minimizasyonu kuralları

1. Başvuru demosunda gerçek TCKN ve sağlık içeriği kullanılmaz.
2. Kabul/ret raporlarında kayıt içeriği yerine fingerprint ve eksik alan adları gösterilir.
3. Secret, token, sertifika ve API anahtarları loglanmaz.
4. Resmî veri sözleşmesinde zorunlu olmadığı doğrulanan alanlar Bakanlığa gönderilmez.
5. Teknik destek erişimleri süreli, kayıtlı ve rol bazlı olmalıdır.

## Başvuru öncesi hukuk/KVKK onay kapıları

- Veri sorumlusu / veri işleyen rollerinin kesinleştirilmesi
- Her veri kategorisi için hukuki sebep
- Saklama süresi ve imha yöntemi
- Aydınlatma ve açık rıza gerekliliği
- Yurt içi/yurt dışı aktarım analizi
- Alt işleyen ve bulut hizmeti sözleşmeleri
- Veri ihlali bildirim prosedürü
