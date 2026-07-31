# KVKK / veri envanteri iskeleti (Faz 0)

Bu belge uygulama içindeki kişisel / özel nitelikli veri kategorilerini özetler.
Resmi Verbis bildirimi ve DPA süreçleri ayrı operasyonel çalışmadır.

## Kimlik ve erişim
| Tablo / alan | Kategori | Not |
|---|---|---|
| `users.email`, `full_name` | Kimlik | Hesap yönetimi |
| `users.hashed_password` | Güvenlik | bcrypt |
| `users.mfa_secret_encrypted` | Güvenlik | Fernet (SECRET_KEY türevli) |
| `password_reset_tokens` | Güvenlik | Hash’lenmiş tek kullanımlık token |

## İşyeri / çalışan
| Tablo / alan | Kategori | Not |
|---|---|---|
| `employees.full_name`, `national_id_masked` | Kimlik | Maskeli TCKN tercih |
| `companies.*` iletişim alanları | İletişim | Adres, telefon, yetkili |

## Sağlık (özel nitelikli)
| Tablo / alan | Kategori | Not |
|---|---|---|
| `health_records.*` | Sağlık | Hekim/DSP erişim rolleri |
| `health_records.confidential_note` | Sağlık (gizli) | Yalnız hekim + EİSA yazma/okuma |

## Operasyon ve denetim
| Tablo / alan | Kategori | Not |
|---|---|---|
| `audit_logs` | İşlem kaydı | IP, kullanıcı, aksiyon |
| `eisa_error_reports` | Destek | Kullanıcı e-posta, stack (kısaltılmış) |
| `eisa_archive_records` / yedek zip | Arşiv | `BACKUP_ENCRYPTION_KEY` ile şifrelenebilir |

## Saklama / erişim ilkeleri (hedef)
- Tenant izolasyonu: OSGB / firma kapsamı
- Minimum yetki: rol bazlı API
- Sağlık gizli alan: hekim yazma kilidi
- MFA: EİSA ve OSGB yöneticileri için zorunlu
- Parola sıfırlama: e-posta token (SMTP)
