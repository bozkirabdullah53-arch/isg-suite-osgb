# Uygulama Navigasyon Denetim Raporu

## Kapsam

Ortak modül yönlendirmesi (`frontend/src/main.jsx`), Risk Analizi iç sekme/detay akışı, Firma 360 ekranı ve uygulamadaki geri/ileri davranışı incelendi. Menü yetki listeleri, aktif işyeri kapsamı, mevcut 5x5 matris ve Fine–Kinney iş mantığı bu çalışmanın kapsamı dışında bırakıldı.

## Bulgular ve düzeltmeler

| Kod | Bulgu | Etki | Durum |
|---|---|---|---|
| NAV-01 | `popstate` boş veya geçersiz modül gördüğünde ana modülü `replaceState` ile yazıyordu. | Risk Analizi gibi modüllerde tarayıcı Geri, önceki uygulama adımı yerine ana sayfaya düşebiliyordu. | Düzeltildi: modül geçmişi indekslendi; geçerli uygulama kaydı geri/ileri ile korunuyor. |
| NAV-02 | Ortak bir “Önceki sayfa” kontrolü yoktu; yalnızca bazı özel ekranlarda yerel geri düğmesi vardı. | Kullanıcı modül içinden güvenilir biçimde önceki ekrana dönemiyordu. | Düzeltildi: kimlik doğrulanmış uygulama başlığına ortak Geri kontrolü eklendi. |
| NAV-03 | Risk sekmeleri ve risk detayı React state’inde kalıyor, tarayıcı geçmişine yazılmıyordu. | Risk listesi → detay veya sekme geçişlerinde Geri, üst modül geçmişine çıkıyordu. | Düzeltildi: `risk_tab` ve `risk_detail` alt rotaları hash geçmişine eklendi. |
| NAV-04 | Firma 360 geçişinde firma kimliği URL/history state içinde taşınmıyordu. | Geri/İleri veya yenileme sonrasında Firma 360 boş açılabiliyordu. | Düzeltildi: `customer_360&company=<id>` ile bağlam korunuyor. |
| NAV-05 | Aynı modüle tekrar tıklamak yeni history kaydı oluşturabiliyordu. | Geri tuşunda boş/tekrarlı adımlar oluşabiliyordu. | Düzeltildi: aynı rota `replaceState` ile tekilleştiriliyor. |
| NAV-06 | Ana modül seçimi ile `popstate` fallback kuralları farklıydı. | Bazı roller geri dönüşte kendi doğru ana ekranı yerine farklı bir başlangıç ekranı görebiliyordu. | Düzeltildi: tek `homeModuleForUser` kuralı kullanılıyor. |

## Korunan alanlar

- Menü yetkileri ve rol bazlı modül görünürlüğü değiştirilmedi.
- Aktif işyeri/tenant kapsamı ve mevcut API filtreleri değiştirilmedi.
- 5x5 matris, Fine–Kinney puanlama ve risk kayıt iş mantığına dokunulmadı.
- Eski `#/risk`, mevcut `#m=risk` ve `?m=risk` bağlantı biçimleri okunmaya devam ediyor.

## Doğrulama

- Navigasyon yardımcıları için 3 regresyon testi eklendi.
- Vite üretim derlemesi başarıyla tamamlandı.
- Özel oturum gerektiren modül geçişleri canlı ortamda yetkili oturum olmadan otomatik doğrulanamadı; canlı public giriş ekranı erişimi ayrıca kontrol edilmelidir.

