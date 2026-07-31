# 04 — Yetki ve İzolasyon Değerlendirmesi

**Kapsam:** İzole QA API smoke, mevcut erişim birim testleri ve kod envanteri. Çok-OSGB senaryosu ile tarayıcı rol testleri bu turda yürütülmedi.

## Rol matrisi

| Rol | Beklenen kapsam | Bu turdaki kanıt | Durum |
| --- | --- | --- | --- |
| Global admin (GA) | Sistem/OSGB çapında yönetim | Login, `/auth/me`, firma ve görevlendirme listesi 200 | Kısmi doğrulandı |
| Company admin (CA) | Kendi firması operasyonu | Login 200; diğer firma personeline erişim 403 | Kısmi doğrulandı |
| İş güvenliği uzmanı | Atandığı işyerleri; sağlık klinik verisi yok | Yıllık plan generate 200; sağlık listesi 403 | Kısmi doğrulandı |
| İşyeri hekimi | Atandığı işyerleri sağlık verisi | Sağlık listesi 200 | Kısmi doğrulandı |
| DSP | Hekimle tanımlı sağlık/personel kapsamı | API senaryosu çalıştırılmadı | Test edilemedi |
| Read-only | Salt özet/görüntüleme | API senaryosu çalıştırılmadı | Test edilemedi |

## IDOR ve tenant izolasyonu

| Vaka | Beklenen | Gözlenen | Sonuç |
| --- | --- | --- | --- |
| CA ile başka firma çalışanları | 403/404 | 403; görevlendirme kapsamı mesajı | Geçti (tek örnek) |
| Tokensız firma listesi | 401 | 401 | Geçti |
| Uzmanın atandığı/atanmadığı firma CRUD’u | Kapsama göre karar | Çalıştırılmadı | Test edilemedi |
| İki OSGB arasında nesne IDOR | Tam izolasyon | Tek `TEST_OSGB` seed bulundu | Test edilemedi |
| Dosya indirme için atama kapsamı | Kapsam doğrulaması | Çalıştırılmadı | Test edilemedi |

`test_company_access.py` içindeki üç birim test erişim kuralını destekler; gerçek HTTP nesne erişimi ve tüm router’lar için kanıt değildir.

## Sağlık gizliliği

| Vaka | Gözlenen | Sonuç |
| --- | --- | --- |
| Uzman → sağlık listesi | 403 | Olumlu ön kanıt |
| Hekim → sağlık listesi | 200 | Beklenen erişim |
| CA → sağlık listesi/tekil kayıt | Çalıştırılmadı | Kritik boşluk |
| Hekim olmayan rol → klinik alanlar ve `confidential_note` | Alan bazlı doğrulanmadı | Kritik boşluk |
| Export/PDF’de sağlık PII | Çalıştırılmadı | Kritik boşluk |

## Hüküm

Bir firma arası personel IDOR örneği ile uzman/hekim ayrımı olumlu sonuç vermiştir. Buna rağmen CA sağlık erişimi, dosya kapsamı, tekil kayıt uçları ve çok-OSGB izolasyonu kanıtlanmadığından izolasyon “tam doğrulandı” olarak değerlendirilemez.
