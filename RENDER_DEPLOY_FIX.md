# Render deploy düzeltmesi

Bu sürüm Render build hatası için hazırlanmıştır.

## Zorunlu işlem

1. Bu klasörün tamamını GitHub deposunun köküne yükleyin.
2. Render servisinde bağlı branch'in bu commit'i kullandığını doğrulayın.
3. Blueprint kullanıyorsanız `render.yaml` için **Sync Blueprint** yapın.
4. Frontend servisi için **Manual Deploy → Clear build cache & deploy** seçin.
5. Backend ortam değişkenlerinde `SEED_ADMIN_EMAIL` ve `SEED_ADMIN_PASSWORD` değerlerini Render panelinden girin.
6. İlk başarılı girişten sonra admin şifresini değiştirin ve `SEED_ADMIN_PASSWORD` değişkenini kaldırın.

## Frontend beklenen ayarlar

- Root Directory: `frontend`
- Build Command: `npm install --global npm@10.8.2 --no-audit --no-fund && npm ci --no-audit --no-fund && npm run build`
- Publish Directory: `dist`
- Node: `20.18.0`

Repo kökünde ve frontend klasöründe `.node-version` / `.nvmrc` dosyaları bulunmaktadır.
