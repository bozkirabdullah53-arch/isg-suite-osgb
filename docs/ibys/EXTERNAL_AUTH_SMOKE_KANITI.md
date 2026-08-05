# İBYS Başvuru Rotaları — Dış Yetkilendirme Smoke Kanıtı

## Sonuç

**Başarılı.** GitHub Actions bağımsız runner’ından staging ortamına kimlik bilgisi olmadan gönderilen isteklerde üç korunan rota da `401 Unauthorized` döndürmüş, yanıt gövdeleri kanıt dosyasına kaydedilmemiş ve başvuru verisi işareti saptanmamıştır.

## Test kimliği

| Alan | Değer |
|---|---|
| Workflow | `IBYS External Authorization Smoke` |
| Workflow run ID | `30982016480` |
| Workflow run sıra no | `2` |
| PR head SHA | `4b6ed8a204d7dfb7c1721185995632d5150e8ccd` |
| Workflow merge SHA | `f2c7c0b8d0bdd3c18057f189d85a54688c15f2de` |
| Hedef | `https://isg-suite-api-staging.onrender.com` |
| Test zamanı (UTC) | `2026-08-05T06:38:07.869494+00:00` |
| Artifact ID | `8920503915` |
| Artifact adı | `ibys-external-auth-smoke-f2c7c0b8d0bdd3c18057f189d85a54688c15f2de` |
| Artifact digest | `sha256:897eb69b95ee1eaaae844cacc81624efe8f2fc0dcff6dabf05d9ce0abc8afb9b` |
| Evidence dosya SHA-256 | `a8529faea8972793c0aded069588d1d6329643806db33943b043d2c111a74efd` |
| Evidence iç mühür | `aecf4aa9d5025cba6ad669416d4e06664eec2098684c3fea50cf37eeb24f73c3` |
| Saklama süresi | 90 gün; `2026-11-03` tarihine kadar GitHub artifact |

## Doğrulanan rotalar

| Metot | Rota | HTTP | Süre | Veri işareti sızıntısı |
|---|---|---:|---:|---|
| GET | `/api/v1/ibys-application/profile` | 401 | 177 ms | Yok |
| GET | `/api/v1/ibys-application/readiness` | 401 | 106 ms | Yok |
| POST | `/api/v1/ibys-application/preflight` | 401 | 89 ms | Yok |

## Güvenlik özellikleri

- Test yalnız anonim isteklerle çalışmıştır.
- Authorization başlığı gönderilmemiştir.
- Credential veya secret kullanılmamıştır.
- Yanıt gövdesi artifact’e yazılmamıştır.
- Dosya checksum’u artifact içinden taşınabilir biçimde `OK` olarak doğrulanmıştır.
- JSON iç `evidence_sha256` mührü bağımsız olarak yeniden hesaplanmış ve eşleşmiştir.
- Workflow ve artifact `official_registration_claim=false` sınırını korumaktadır.

## Kapsam sınırı

Bu kanıt yalnız staging ortamındaki başvuru rotalarının anonim erişime kapalı olduğunu gösterir. Bakanlık tescili, resmî İBYS veri sözleşmesi uygunluğu veya canlı Bakanlık veri gönderimi anlamına gelmez.
