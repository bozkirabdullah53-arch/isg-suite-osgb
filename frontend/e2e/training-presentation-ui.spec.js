import {test, expect} from '@playwright/test';

const readyPayload = {
  readiness_version: 'nace-training-presentation-readiness-v3',
  training_id: 101,
  company_id: 35,
  enabled: true,
  visible: true,
  read_only: true,
  manifest_preview_supported: true,
  generation_supported: true,
  generation_allowed: true,
  renderer_version: 'nace-training-presentation-renderer-v1',
  core_training_unaffected: true,
  classification: {
    status: 'verified',
    nace_code: '62.01.01',
    nace_description: 'Bilgisayar programlama faaliyetleri',
    hazard_class: 'Az Tehlikeli',
  },
  checks: [
    {code: 'feature_flag', label: 'Sunum özelliği', ok: true, detail: 'Açık'},
    {code: 'verified_nace_snapshot', label: 'Doğrulanmış NACE snapshot', ok: true, detail: 'Hazır'},
    {code: 'five_training_topics', label: 'Beş işe özgü eğitim konusu', ok: true, detail: 'Hazır'},
    {code: 'technical_risks', label: 'Teknik risk etiketleri', ok: true, detail: 'Hazır'},
    {code: 'exact_exam_readiness', label: 'NACE uyumlu sınav içeriği', ok: true, detail: '5 + 15 hazır'},
    {code: 'training_not_cancelled', label: 'Eğitim durumu', ok: true, detail: 'Aktif'},
    {code: 'template_contract', label: 'İçerik ve şablon sözleşmesi', ok: true, detail: 'Onaylı'},
    {code: 'presentation_renderer', label: 'PPTX/PDF üretim servisi', ok: true, detail: 'Hazır'},
  ],
  blockers: [],
  warnings: [],
  next_action: 'Yeni sunum sürümü oluşturabilirsiniz.',
};

const manifestPayload = {
  content_hash: 'a'.repeat(64),
  nace_snapshot: {nace_code: '62.01.01'},
  slides: Array.from({length: 21}, (_, index) => ({
    position: index + 1,
    section_id: index === 0 ? 'cover' : 'work_specific_topics',
    title: index === 0 ? 'Temel İş Sağlığı ve Güvenliği Eğitimi' : `Sunum slaytı ${index + 1}`,
    approval_required: index === 0 || index === 16 || index === 17,
  })),
};

async function installRoutes(page, readiness = readyPayload) {
  let readinessCalls = 0;
  let versionCalls = 0;
  await page.route('**/health', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: '{"ok":true}'});
  });
  await page.route('**/api/v1/trainings/101/presentation-readiness', async (route) => {
    readinessCalls += 1;
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(readiness)});
  });
  await page.route('**/api/v1/trainings/101/presentation-versions', async (route) => {
    versionCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({training_id: 101, count: 0, rows: [], read_only_history: true}),
    });
  });
  await page.route('**/api/v1/trainings/101/presentation-manifest-preview', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(manifestPayload)});
  });
  return {
    readinessCalls: () => readinessCalls,
    versionCalls: () => versionCalls,
  };
}

async function injectTrainingOutput(page) {
  await page.evaluate(() => {
    document.body.innerHTML = `
      <main style="width:100%;max-width:100%;padding:12px">
        <section class="education-output-panel panel">
          <h3>Eğitim Belgesi ve PDF Raporlama</h3>
          <p>Kayıt #101 · 2 katılımcı üzerinden PDF çıktıları hazır.</p>
          <button type="button">Sertifika PDF</button>
        </section>
      </main>`;
  });
}

test('flag disabled keeps the existing training output unchanged', async ({page}) => {
  await installRoutes(page, {...readyPayload, enabled: false, visible: false, generation_allowed: false});
  await page.goto('/');
  await injectTrainingOutput(page);
  await page.waitForTimeout(450);

  await expect(page.locator('.education-output-panel')).toBeVisible();
  await expect(page.locator('.training-presentation-panel')).toHaveCount(0);
  await expect(page.getByText('Sertifika PDF')).toBeVisible();
});

test('ready panel renders once, exposes actions and opens a read-only preview', async ({page}) => {
  const calls = await installRoutes(page);
  await page.goto('/');
  await injectTrainingOutput(page);

  const panel = page.locator('.training-presentation-panel');
  await expect(panel).toBeVisible();
  await expect(panel.getByText('NACE Uyumlu Eğitim Sunumu')).toBeVisible();
  await expect(panel.getByText('Sunum Taslağı Oluştur')).toBeVisible();
  await expect(panel.getByText('İçerik Önizlemesi')).toBeVisible();
  await expect(panel.getByText('Eğitim, 20 soruluk sınav')).toBeVisible();

  const mutations = await page.evaluate(() => {
    window.__presentationMutationCount = 0;
    const parent = document.querySelector('.training-presentation-panel')?.parentElement;
    if (!parent) return false;
    const observer = new MutationObserver((entries) => {
      window.__presentationMutationCount += entries.length;
    });
    observer.observe(parent, {childList: true, subtree: true, characterData: true});
    window.__presentationMutationObserver = observer;
    return true;
  });
  expect(mutations).toBe(true);
  await page.waitForTimeout(650);
  const mutationCount = await page.evaluate(() => window.__presentationMutationCount || 0);
  expect(mutationCount).toBeLessThanOrEqual(2);
  expect(calls.readinessCalls()).toBeLessThanOrEqual(1);
  expect(calls.versionCalls()).toBeLessThanOrEqual(1);

  await panel.getByText('İçerik Önizlemesi').click();
  const dialog = page.locator('.training-presentation-preview');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('21 slayt')).toBeVisible();
  await expect(dialog.getByText('Sunum slaytı 21')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
});

test('mobile panel and preview do not create horizontal page overflow', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await installRoutes(page);
  await page.goto('/');
  await injectTrainingOutput(page);

  const panel = page.locator('.training-presentation-panel');
  await expect(panel).toBeVisible();
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    panelWidth: document.querySelector('.training-presentation-panel')?.getBoundingClientRect().width || 0,
    buttons: [...document.querySelectorAll('.training-presentation-panel__button')].map((button) => ({
      width: button.getBoundingClientRect().width,
      height: button.getBoundingClientRect().height,
    })),
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewport);
  expect(dimensions.panelWidth).toBeLessThanOrEqual(dimensions.viewport);
  expect(dimensions.buttons.length).toBeGreaterThan(0);
  for (const button of dimensions.buttons) {
    expect(button.height).toBeGreaterThanOrEqual(44);
  }

  await panel.getByText('İçerik Önizlemesi').click();
  await expect(page.locator('.training-presentation-preview')).toBeVisible();
  const dialogBox = await page.locator('.training-presentation-preview__card').boundingBox();
  expect(dialogBox).not.toBeNull();
  expect(dialogBox.x).toBeGreaterThanOrEqual(0);
  expect(dialogBox.x + dialogBox.width).toBeLessThanOrEqual(390);
  expect(dialogBox.y).toBeGreaterThanOrEqual(0);
  expect(dialogBox.y + dialogBox.height).toBeLessThanOrEqual(844);
});
