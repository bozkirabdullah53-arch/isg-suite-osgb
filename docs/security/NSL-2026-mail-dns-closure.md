# NSL-202602 / 202606 / 202607 — posta ve DNS kapanış planı (2026-10-16)

Kaynak: YONCERT NSL-2026-PRJ-097 V1.0. Uygulama bulguları (601, 603–605, 608, 609)
önceki yayınlarda ele alındı; bu belge kalan üç posta/DNS bulgusunu kapatır.

## 16 Ekim 2026 tespiti (salt okunur)

| Kontrol | Sonuç |
|---|---|
| `isgsuite.tr` MX | `1 smtp.google.com` — gelen posta Google Workspace'te |
| `isgsuite.tr` SPF | `v=spf1 include:_spf.google.com ~all` |
| `_dmarc.isgsuite.tr` | `v=DMARC1; p=none; rua=mailto:info@isgsuite.tr; adkim=s; aspf=s` |
| `google._domainkey.isgsuite.tr` | Yok — DKIM imzası yayımlanmamış |
| Uygulama SMTP (canlı render.yaml) | `giden.mailmatik.com:465` (93.89.227.30). SPF'de yok, DKIM yok, yani uygulama e-postaları DMARC'tan geçmiyor. DMARC sıkılaştırılırsa şifre sıfırlama ve MFA e-postaları düşer. |
| Uygulama gelen posta (canlı render.yaml) | `pop3.isgsuite.tr:110`, TLS yok. **Parola her senkronda düz metin gidiyor.** MX Google'da olduğu için bu kutuya yeni posta da gelmiyor. |
| Eski İsimtescil kayıtları | `mail` / `webmail` 93.89.226.88 (IIS 7.5, ASP.NET 2.0, MailEnable 9.51), `smtp` 93.89.226.86, `pop3` 93.89.226.87, `mx01` 93.89.226.79 hâlâ internete açık |
| `isgsuite.com.tr` | MX `mail.isgsuite.com.tr` (93.89.226.88, aynı EOL sunucu), SPF yok, DMARC yok. Bu alan adı yalnız site için kullanılıyor (sahibi doğruladı). |

## Kod değişikliği (bu dal)

- `backend/app/services/inbound_mail.py`: POP3'te STLS, IMAP'te STARTTLS **zorunlu**,
  sertifika ve alan adı doğrulaması açık. TLS kurulamazsa kullanıcı adı ve parola
  **hiç gönderilmez**, senkron hata verir. Başarısız bağlantılar kaynaklarını
  serbest bırakır. Bu değişiklik PR #473'ten alındı.
- `render.yaml`: SMTP `smtp.gmail.com:465` (SSL), gelen posta `imap.gmail.com:993` (SSL, IMAP).
  IMAP senkronu salt okunur çalışır: Gmail'de mesaj silmez, okundu olarak işaretlemez.
- Testler: `test_inbound_mail_tls*`, `test_email_inbox`, `test_email_delivery_tracking`: 27 test geçti.

## Uygulama sırası — çalışan sistemi bozmamak için sıra önemli

### 1. Google tarafı (yaklaşık 10 dk, ücretsiz)
1. info@isgsuite.tr hesabında **2 Adımlı Doğrulama** açık olmalı.
2. myaccount.google.com → Güvenlik → **Uygulama şifreleri** → "isgsuite-render" adıyla oluştur.
   Menü görünmüyorsa Admin konsolu → Güvenlik → 2 Adımlı Doğrulama'da kullanıcıların
   2SV açmasına izin verildiğini kontrol et.
3. Gmail → Ayarlar → Yönlendirme ve POP/IMAP → **IMAP etkin**.
4. Admin konsolu → Uygulamalar → Google Workspace → Gmail → **E-postanın kimliğini doğrula**
   → `isgsuite.tr` → **Yeni kayıt oluştur** (2048 bit, seçici `google`). Kaydı kopyala.
   "Kimlik doğrulamayı başlat" düğmesine **adım 3'teki DNS kaydı yayımlandıktan sonra** bas.

### 2. Render (API servisi → Environment) — kod birleşmeden ÖNCE
| Anahtar | Değer |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` |
| `SMTP_USE_SSL` / `SMTP_USE_TLS` | `true` / `false` |
| `SMTP_PASSWORD` | Google uygulama şifresi |
| `INBOUND_MAIL_HOST` / `PORT` | `imap.gmail.com` / `993` |
| `INBOUND_MAIL_USE_SSL` / `PROTOCOL` | `true` / `imap` |
| `INBOUND_MAIL_PASSWORD` | aynı uygulama şifresi |

Kaydet, servisi yeniden başlat. **Kontrol:** bir test hesabına şifre sıfırlama e-postası
gönder, gelen e-postada Gmail → "Orijinali göster" ekranında `SPF: PASS`, `DKIM: PASS`
(adım 3'ten sonra) ve `DMARC: PASS` görünmeli. EİSA gelen kutusu senkronunu bir kez çalıştır.
Bu adım bitince PR birleştirilir. Böylece render.yaml canlı ayarla aynı olur.

### 3. DNS — İsimtescil paneli (dnsenable)
**isgsuite.tr**
| İşlem | Kayıt |
|---|---|
| EKLE | TXT `google._domainkey` → Google'ın verdiği `v=DKIM1; k=rsa; p=...` |
| KORU | TXT `@` → `v=spf1 include:_spf.google.com ~all` |
| KORU | MX → `smtp.google.com` |
| SİL (2. adım doğrulandıktan sonra) | A `mail`, `webmail`, `smtp`, `pop3`, `mx01` (93.89.226.x) ve varsa `autodiscover`/`imap` CNAME'leri |
| DEĞİŞTİR (1 hafta DMARC raporu temizse) | TXT `_dmarc` → `v=DMARC1; p=quarantine; rua=mailto:info@isgsuite.tr; adkim=s; aspf=s` |
| DEĞİŞTİR (2 hafta daha temizse) | `p=reject` |

**isgsuite.com.tr** (posta kullanılmıyor)
| İşlem | Kayıt |
|---|---|
| SİL | MX `mail.isgsuite.com.tr`, A `mail` |
| EKLE | MX `@` → öncelik `0`, hedef `.` (null MX, RFC 7505; panel kabul etmezse bu satırı atla) |
| EKLE | TXT `@` → `v=spf1 -all` |
| EKLE | TXT `_dmarc` → `v=DMARC1; p=reject; adkim=s; aspf=s` |

Site kayıtlarına (A `@` → 216.24.57.1, `www` CNAME → isg-suite-web-1u9t.onrender.com) **dokunulmaz**.

### isgsuite.com.tr sitesi (aynı depo, aynı servis)
DNS doğru, ancak 16 Ekim'de `https://www.isgsuite.com.tr` TLS el sıkışmasında başarısızdı:
Render'da bu alan adı için sertifika yok. Render → `isg-suite-web` → Settings → Custom Domains →
`www.isgsuite.com.tr` ekle (Render kök `isgsuite.com.tr` → www yönlendirmesini kendisi ekler),
"Verify" de ve sertifika "Issued" olana kadar bekle. render.yaml'a da eklendi.
CAPTCHA açılacaksa `TURNSTILE_ALLOWED_HOSTNAMES` ve Turnstile widget'ına
`www.isgsuite.com.tr` de eklenmeli. Şifre sıfırlama bağlantıları `FRONTEND_ORIGIN`
(www.isgsuite.tr) adresine gider; iki alan adı aynı veritabanını kullandığı için bu sorun değildir.

### 4. İsimtescil posta paketi
Adım 2 ve 3'teki kontroller geçtikten sonra İsimtescil'deki e-posta barındırma paketi
iptal edilir. Eski kutuda saklanması gereken posta varsa önce Gmail'e aktarılır
(Gmail → Ayarlar → Hesaplar → "Postaları ve kişileri içe aktar").
Ayrıca eski İsimtescil posta parolası düz metin dolaştığı için o parola artık
hiçbir yerde (başka hesaplarda) kullanılmamalı.

## Kapanış kanıtı

```
dig +short TXT google._domainkey.isgsuite.tr      # DKIM kaydı
dig +short TXT _dmarc.isgsuite.tr                 # p=quarantine/reject
dig +short A mail.isgsuite.tr smtp.isgsuite.tr    # boş
dig +short MX isgsuite.com.tr                     # boş veya "0 ."
dig +short TXT _dmarc.isgsuite.com.tr             # p=reject
curl -sI http://mail.isgsuite.tr                  # çözümlenmemeli
```

| Bulgu | Kapanış koşulu |
|---|---|
| NSL-202602 | Uygulama parolayı yalnız TLS ile gönderir (kod). Eski düz metin uçlar alan adından kaldırıldı. |
| NSL-202607 | EOL MailEnable/IIS sunucusu artık isgsuite.tr / isgsuite.com.tr adı altında değil. Paket iptal edildi. |
| NSL-202606 | Her iki alan adında DMARC var, isgsuite.tr DKIM imzalı ve politika quarantine/reject. |

Yeniden testi YONCERT'in yapması gerekir. Bu belgedeki gözlemler dış kapanış onayı yerine geçmez.
