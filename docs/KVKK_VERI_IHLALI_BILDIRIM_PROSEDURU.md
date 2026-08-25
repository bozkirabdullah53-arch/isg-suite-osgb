# Kişisel Veri İhlali Bildirim Prosedürü (DPA)

**Doküman sürümü:** 1.0
**Tarih:** 26 Ağustos 2026
**Sahibi:** [Firma adı doldurulacak]
**İlgili mevzuat:** 6698 sayılı KVKK md.12 ve Kişisel Verilerin İhlali Halinde
Müdahale ve Bildirim Rehberi (KVKK)

---

## 1. Amaç ve Kapsam

Kişisel verilerin yasadışı işlenmesi, yetkisiz erişim, kayıp, ifşa veya değiştirilmesi
durumunda müdahale, bildirim ve iyileştirme süreçlerini tanımlar.

## 2. Veri İhlali Tanımı

Aşağıdakilerden herhangi biri **veri ihlali** kabul edilir:
- Yetkisiz kişi erişimi (veritabanı, depolama, yedek)
- Veri ifşası (açık metin sızma, loglara yazılma)
- Veri kaybı (yanlış silme, depolama arızası)
- Veri bütünlüğü bozulması (yetkisiz değişiklik, şifre çözme başarısızlığı)
- Hesap ele geçirme (credential sızıntısı, token kötüye kullanım)

## 3. İhlal Tespiti ve İlk Müdahale

1. **Tespit:** İhlal izleme/kontrol, kullanıcı bildirimi, denetim veya otomatik alarm
   ile tespit edilir (ör. token_revoke, audit_logs, rate-limit alarm).
2. **İlk değerlendirme (72 saat içinde):** İhlalin kapsamı, etkilenen veriler, etkilenen
   kişi sayısı ve risk seviyesi belirlenir.
3. **Kapsama alma:** İhlal kaynağı kapatılır/yalıtılır (hesap askıya alma, token
   iptali `logout-all`, erişim engeli, IP blok).

## 4. Bildirim Yükümlülükleri

### 4.1 Kurula bildirim (KVKK md.12/337 değişikliği)
İhlal, ilgili kişilerin hakları veya özgürlükleri açısından **risk oluşturuyorsa**,
en geç ihlalin tespit edilmesinden **72 saat** içinde KVK Kuruluna bildirim yapılır.

### 4.2 İlgili kişilere bildirim
İhlal yüksek risk oluşturuyorsa (ör. özel nitelikli sağlık/TCKN ifşası), etkilenen
kişilere **ayrıca** bildirim yapılır (KVKK md.12/337).

**Bildirim içeriği:**
- İhlalin niteliği
- Etkilenen kişisel veriler
- Olası sonuçlar
- Alınan/acılacak tedbirler
- İlgili kişinin hakları ve iletişim kanalı

### 4.3 ÇSGB'ye bildirim (Gizlilik Sözleşmesi)
Gizlilik Sözleşmesi md.3.11: Verilerin hukuka aykırı işlenmesi/ifşası halinde firma
tazminat sorumluluğunu kabul eder. Bakanlık, ihlalin ortadan kaldırılması için
duyuru yapabilir. İBYS verisiyle ilgili ihlal **ÇSGB/İSGGM'ye derhal** bildirilir.

## 5. İyileştirme ve Sonuç

1. **Kök neden analizi:** İhlalin nasıl oluştuğu belirlenir.
2. **Düzeltme:** Zafiyet/eksiklik giderilir (kod, altyapı, süreç).
3. **Tekrar test:** Düzeltmenin etkinliği doğrulanır (SAST/DAST/smoke test).
4. **Kayıt:** İhlal raporu (tespit, müdahale, bildirim, sonuç) arşivlenir ve denetime
   hazır tutulur.

## 6. Roller

| Rol | Sorumluluk |
|---|---|
| Veri Sorumlusu temsilcisi | Bildirim kararı, Kurula/kişilere/ÇSGB'ye bildirim |
| Sistem yöneticisi | Teknik müdahale, kapsama alma, kök neden |
| Hukuk danışmanı | Bildirim içeriği ve yasal yükümlülük değerlendirmesi |

## 7. İhlal Sınıflandırması (Risk Matrisi)

| Risk | Örnek | Bildirim |
|---|---|---|
| Düşük | Tek kişi, kamu verisi, sınırlı erişim | İç kayıt |
| Orta | Birden çok kişi, iletişim verisi | Kurula bildirim |
| Yüksek | Sağlık/TCKN ifşası, geniş kitle | Kurula + kişilere + ÇSGB |

## 8. Referanslar

- KVKK 6698 md.12 (Kişisel verilerin güvenliğine ilişkin yükümlülükler)
- KVKK İhlal Bildirim Rehberi (KVKK)
- Gizlilik Sözleşmesi md.3.11 (ifşa sorumluluğu)
- Kod: `backend/app/services/token_revoke.py` (token iptali),
  `backend/app/api/security.py` (audit-logs, MFA, hesap askıya)
