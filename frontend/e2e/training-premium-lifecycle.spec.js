import {test, expect} from '@playwright/test';

const premiumPolicy = {
  enabled: true,
  version: 'training-premium-lifecycle-v2',
  checked_at: '2026-08-09',
  rules: {
    initial_basic: {hours: {'Az Tehlikeli': 8, Tehlikeli: 12, 'Çok Tehlikeli': 16}},
    repeat_basic: {hours: {'Az Tehlikeli': 8, Tehlikeli: 8, 'Çok Tehlikeli': 8}},
    work_specific: {hours: {'Az Tehlikeli': 2, Tehlikeli: 3, 'Çok Tehlikeli': 4}},
    lesson_definition: '45 dakika ders + 15 dakika ara dinlenmesi',
  },
};

async function installPolicy(page, lifecycle) {
  await page.route('**/api/v1/trainings/premium-policy', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(premiumPolicy),
  }));
  await page.route(`**/api/v1/trainings/${lifecycle.training_id}/premium-lifecycle`, (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(lifecycle),
  }));
  await page.route('**/health', (route) => route.fulfill({status: 200, contentType: 'application/json', body: '{"ok":true}'}));
}

async function injectTrainingPage(page, trainingId) {
  await page.evaluate((id) => {
    document.body.innerHTML = `
      <main class="training-pro">
        <div class="tp-tabs"><button type="button">Temel İSG Eğitimi</button></div>
        <section class="panel-card">
          <div>
            <label class="tp-label">Eğitim türü</label>
            <select class="tp-select">
              <option value="İlk Defa">İlk Defa</option>
              <option value="Tekrar">Tekrar</option>
              <option value="Temel İSG Eğitimi">Temel İSG Eğitimi</option>
            </select>
          </div>
          <div>
            <label class="tp-label">Tehlike sınıfı</label>
            <select class="tp-select"><option value="Çok Tehlikeli" selected>Çok Tehlikeli</option></select>
          </div>
          <div class="tp-grid-2">
            <label class="check-box"><input type="checkbox" checked><span><strong>Katılım doğrulandı</strong></span></label>
            <label class="check-box"><input type="checkbox" checked><span><strong>Başarı koşulu sağlandı</strong></span></label>
          </div>
          <section class="education-output-panel">
            <p>Kayıt #${id} · 2 katılımcı üzerinden PDF çıktıları hazır.</p>
            <button type="button">Sertifika PDF (Katılım Belgeleri)</button>
            <button type="button">Sınav Oluştur (20 Soru)</button>
            <button type="button">Katılım PDF (İmza Formu)</button>
          </section>
        </section>
      </main>`;
  }, trainingId);
}

test('premium work-start UI is simple, Turkish and cannot expose Basic İSG outputs', async ({page}) => {
  const lifecycle = {
    training_id: 901,
    premium_enforced: true,
    stage: 'planned',
    stage_label: 'Planlandı',
    next_action: 'Eğitim günü geldiğinde katılımı kaydedin.',
    policy: {kind: 'work_start'},
  };
  await installPolicy(page, lifecycle);
  await page.goto('/');
  await injectTrainingPage(page, 901);

  await expect(page.getByRole('heading', {name: 'Planla → Gerçekleştir → Sonuçlandır → Belgelendir'})).toBeVisible();
  await expect(page.getByText('İlk temel eğitim 16 ders saati', {exact: false})).toBeVisible();
  await expect(page.getByText('tekrar temel eğitim 8 ders saati', {exact: false})).toBeVisible();
  await expect(page.getByText('işe özgü bölüm en az 4 ders saati', {exact: false})).toBeVisible();
  await expect(page.getByText('Katılım ve başarı şimdi onaylanmaz', {exact: false})).toBeVisible();

  const type = page.locator('select.tp-select').first();
  await expect(type.locator('option[value="İşe Başlama Eğitimi"]')).toHaveCount(1);
  await expect(type.locator('option[value="Bilgi Yenileme Eğitimi"]')).toHaveCount(1);
  await expect(type.locator('option[value="Tekrar"]')).toHaveText(/en az 8 ders saati/);

  await expect(page.getByRole('button', {name: /Sertifika PDF/})).toBeDisabled();
  await expect(page.getByRole('button', {name: /Sınav Oluştur/})).toBeDisabled();
  await expect(page.getByRole('button', {name: /İşe Başlama Eğitimi Tutanağı PDF/})).toBeEnabled();
  await expect(page.getByText('İşe Başlama Eğitimi, Temel İSG Eğitimi değildir', {exact: false})).toBeVisible();
  await expect(page.getByText('Planlandı', {exact: true})).toBeVisible();
});

test('premium layer leaves Basic İSG output actions working', async ({page}) => {
  const lifecycle = {
    training_id: 902,
    premium_enforced: true,
    stage: 'planned',
    stage_label: 'Planlandı',
    next_action: 'Eğitim günü geldiğinde katılımı kaydedin.',
    policy: {kind: 'initial_basic'},
  };
  await installPolicy(page, lifecycle);
  await page.goto('/');
  await injectTrainingPage(page, 902);

  await expect(page.getByRole('button', {name: /Sertifika PDF/})).toBeEnabled();
  await expect(page.getByRole('button', {name: /Sınav Oluştur/})).toBeEnabled();
  await expect(page.getByRole('button', {name: /Katılım PDF/})).toBeEnabled();
  await expect(page.getByText('İşe Başlama Eğitimi, Temel İSG Eğitimi değildir', {exact: false})).toHaveCount(0);
});

test('premium lifecycle fits a 390px mobile viewport', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await installPolicy(page, {
    training_id: 903,
    premium_enforced: true,
    stage: 'planned',
    stage_label: 'Planlandı',
    next_action: 'Eğitim günü geldiğinde katılımı kaydedin.',
    policy: {kind: 'work_start'},
  });
  await page.goto('/');
  await injectTrainingPage(page, 903);
  await expect(page.locator('.training-premium-lifecycle')).toBeVisible();
  const widths = await page.evaluate(() => ({
    viewport: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
  }));
  expect(widths.documentWidth).toBeLessThanOrEqual(widths.viewport);
});