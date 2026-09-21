# Güvenlik Altyapı Geçişi — F-01 (SMTP TLS), F-05 (ClamAV), F-06 (Redis)

Hazırlık tarihi: 2026-09-21 · Kaynak: dış güvenlik değerlendirmesi (rapor §6.5)
İlke: **çalışan uygulamayı bozmadan** geçiş — her adım bayraklı, doğrulamalı ve geri alınabilir.

---

## 1) F-01 — Brevo SMTP Relay (parola sıfırlama maillerini şifreli taşı)

Sorun: mevcut sağlayıcı (isimtescil "Mail Server 2") hiçbir TLS portunu desteklemiyor
(2026-09-21 probe: 587 STARTTLS yok, 465/993/995 kapalı, POP3 CAPA'da STLS yok).

### Adımlar
1. Brevo hesabı açın (ücretsiz katman: günde 300 mail).
2. Brevo → **Senders & Domains** → `isgsuite.tr` domain'ini ekleyin; verilen
   **DKIM (TXT)** ve **Brevo SPF (TXT)** kayıtlarını DNS'e ekleyip doğrulayın.
3. Brevo → **SMTP & API** → SMTP kimlik bilgilerini alın (login + SMTP key).
4. Render Dashboard → `isg-suite-api` → Environment:
   - `SMTP_HOST=smtp-relay.brevo.com`
   - `SMTP_PORT=587`
   - `SMTP_USE_TLS=true`  (SMTP_USE_SSL=false kalsın)
   - `SMTP_USERNAME=<Brevo SMTP login>`
   - `SMTP_PASSWORD=<Brevo SMTP key>` (secret)
   - `SMTP_FROM_EMAIL=info@isgsuite.tr` (domain doğrulanmış olmalı)
5. Kaydet → servis yeniden başlar (kod değişikliği YOK; `mailer.py` STARTTLS destekli).

### Doğrulama
- Uygulamadan "şifremi unuttum" → mail geliyor mu?
- Brevo → Logs → delivery durumu; API delivery log satırı `status=sent`.

### Geri alma
Aynı env alanlarını eski değerlere döndürün: `mail.isgsuite.tr / 587 / USE_TLS=false`.

### Gelen kutusu (INBOUND) notu
Gelen kutusu hâlâ `pop3.isgsuite.tr:110` (düz metin) — sağlayıcı POP3S/IMAPS vermiyor.
Kalıcı çözüm: mailbox'ı TLS destekli sağlayıcıya taşıyıp `INBOUND_MAIL_*` değerlerini
IMAPS (993/SSL, `INBOUND_MAIL_PROTOCOL=imap`) olarak güncellemek. **Dikkat:** protokol
değişiminde `imap_uid` eşlemesi değiştiğinden geçmiş mailler yeniden senkron olabilir
(UI'da tekrar görünebilir) — geçişi bakım penceresinde yapın.

---

## 2) F-05 — ClamAV (yüklenen dosyalarda gerçek imza taraması)

Mevcut durum: production'da `UPLOAD_GATEWAY_ENABLED=true` + magic-byte/uzantı filtresi;
gerçek AV taraması yalnızca `CLAMAV_HOST` doluysa. `CLAMAV_REQUIRED=false`.

### Yerel/test (hazır)
```bash
docker compose --profile clamav up -d clamav
export CLAMAV_HOST=clamav CLAMAV_PORT=3310
```
Test: EICAR dosyası yükle → gateway reddetmeli.

### Production (Render)
1. ClamAV'ı çalıştırma seçeneklerinden birini seçin:
   a. **Ayrı küçük bir VM/container** (Hetzner/Fly/OCI) üzerinde `clamav/clamav:stable`,
      clamd portunu (3310) yalnız Render dış ağına/VPN'e açık tutun.
   b. Render **Private Service**: bu repoya `clamav/Dockerfile` (FROM clamav/clamav:stable)
      ekleyip blueprint'e `type: pserv` servisi tanımlayın (ücretlidir; RAM ≥1GB).
      İnternet'e AÇMAYIN — private service endpoint'i yalnız iç ağdan erişilir.
2. `isg-suite-api` env: `CLAMAV_HOST=<private hostname>`, `CLAMAV_PORT=3310`.
3. Doğrulama: EICAR testi + loglarda `clamd scan ok`.
4. Son adım: `CLAMAV_REQUIRED=true` → artık host yoksa production **başlamaz**
   (fail-closed; `config.py validate_runtime_settings`).

### Geri alma
`CLAMAV_REQUIRED=false` (+ gerekirse `CLAMAV_HOST` boş) → magic-byte modu devam eder.

---

## 3) F-06 — Redis (paylaşımlı rate-limit)

Mevcut durum: `REDIS_URL` boş → bellek içi limit (instance başına). Kod hazır:
`rate_limit.py` Redis varsa `INCR` tabanlı paylaşım kullanıyor; Redis hata verirse
otomatik bellek içi yedeğe düşer (deploy'u kırmaz).

### Production (Render Key Value)
1. Render Dashboard → **New +** → **Key Value (Redis)** → instance oluşturun
   (ücretlidir; en küçük plan yeterli) — aynı bölgesel ağda olsun.
2. `isg-suite-api` env: `REDIS_URL=<internal rediss URL>`.
3. Doğrulama: auth login endpoint'ine iki instance'lı kurulumda toplam
   `RATE_LIMIT_AUTH_RPM` (30/dk) aşımında `429 + Retry-After` gözleyin.
4. Yerel test: `docker compose --profile redis up -d` + `REDIS_URL=redis://redis:6379/0`.

### Geri alma
`REDIS_URL` sil/boşalt → bellek içi moda döner (davranış bugünküyle aynı).

---

## Öncelik sırası önerisi
1. **F-01 Brevo** (en yüksek risk: token'lar düz metin) — 30-45 dk
2. **F-06 Redis** (tek tıkla KV + env) — 15 dk
3. **F-05 ClamAV** (servis provision gerektirir) — 1-2 saat
