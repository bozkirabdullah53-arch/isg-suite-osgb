# Faz 5 Kullanım Rehberi

Bu paket Faz 1–5'in tamamını tek proje içinde içerir.

## Eklenen özellikler

- Gerçek doküman dosyası yükleme
- Güvenli dosya türü ve boyut kontrolü
- Firma bazlı güvenli dosya indirme
- Personel listesini Excel'e aktarma
- İSG kayıt özetini PDF'e aktarma
- Kullanıcının kendi şifresini değiştirmesi
- Denetim kayıtları
- Güvenlik ve dışa aktarım ekranları
- Temel smoke test

## Dosya yükleme sınırları

Desteklenen türler:

- PDF
- Excel
- Word
- PNG
- JPG/JPEG

Varsayılan üst sınır 10 MB'dir.

## Üretim ortamı uyarısı

Yerel disk Render gibi platformlarda kalıcı olmayabilir. Canlı kullanım için:

- AWS S3
- Cloudflare R2
- Azure Blob Storage
- Google Cloud Storage

gibi kalıcı nesne depolama hizmetlerinden biri kullanılmalıdır.

Dosya tarama için ClamAV veya harici zararlı yazılım tarama servisi eklenmelidir.

## Güvenlikte kalan işler

- MFA
- E-posta doğrulama
- Parola sıfırlama
- Rate limiting
- Oturum iptali / refresh token
- Merkezi secret manager
- Tam kapsamlı audit trail
- KVKK veri saklama ve anonimleştirme motoru
