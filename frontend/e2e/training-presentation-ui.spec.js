import {test, expect} from '@playwright/test';

const readyPayload = {
  readiness_version: 'nace-training-presentation-readiness-v4',
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
  rollout: {
    global_enabled: true,
    force_off: false,
    allowlist_configured: true,
    pilot_company: true,
    active: true,
  },
  classification: {
    status: 'verified',
    nace_code: '62.01.01',
    nace_description: 'Bilgisayar programlama faaliyetleri',
    hazard_class: 'Az Tehlikeli',
  },
  checks: [
    {code: 'feature_flag', label: 'Kontrollü pilot erişimi', ok: true, detail: 'Hazır'},
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

function generatedVersion() {
  return {
    id: 501,
    training_id: 101,
    company_id: 35,
    version: 1,
    status: 'generated',
    manifest_hash: 'a'.repeat(64),
    outputs: {
      pptx: {storage_key: 'pilot/v1.pptx', file_hash: 'b'.repeat(64), file_size: 1048576},
      pdf: {storage_key: 'pilot/v1.pdf', file_hash: 'c'.repeat(64), file_size: 2048},
    },
    failure: {},
    created_at: '2026-08-06T06:00:00Z',
    generated_at: '2026-08-06T06:01:00Z',
  };
}

async function installRoutes(page, {readiness = readyPayload, initialRows = []} = {}) {
  let readinessCalls = 0;
  let versionCalls = 0;
  let approvalBody = null;
  let rows = [...initialRows];
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
      body: JSON.stringify({training_id: 101, count: rows.length, rows, read_only_history: true}),
    });
  });
  await page.route('**/api/v1/trainings/101/presentation-manifest-preview', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(manifestPayload)});
  });
  await page.route('**/api/v1/trainings/101/presentation-versions/501/approve', async (route) => {
    approvalBody = route.request().postDataJSON();
    const approval = {
      id: 901,
      presentation_version_id: 501,
      training_id: 101,
      company_id: 35,
      approval_method: approvalBody.approval_method,
      hashes: {manifest: 'a'.repeat(64), pptx: 'b'.repeat(64), pdf: 'c'.repeat(64)},
      approver: {user_id: 9, name: 'Pilot İSG Uzmanı', role: 'safety_specialist'},
      legal_notice: 'Bu kayıt uygulama içi uzman onayıdır; nitelikli elektronik imza yerine geçmez.',
      event_hash: 'd'.repeat(64),
      created_at: '2026-08-06T06:02:00Z',
      immutable: true,
    };
    rows = [{...rows[0], status: 'approved', approved_at: approval.created_at, approval}];
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({version: rows[0], approval}),
    });
  });
  return {
    readinessCalls: () => readinessCalls,
    versionCalls: () => versionCalls,
    approvalBody: () => approvalBody,
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
  await installRoutes(page, {
    readiness: {
      ...readyPayload,
      enabled: false,
      visible: false,
      generation_allowed: false,
      rollout: {...readyPayload.rollout, global_enabled: false, active: false},
    },
  });
  await page.goto('/');
  await injectTrainingOutput(page);
  await page.waitForTimeout(450);

  await expect(page.locator('.education-output-panel')).toBeVisible();
  await expect(page.locator('.training-presentation-panel')).toHaveCount(0);
  await expect(page.getByText('Sertifika PDF')).toBeVisible();
});

test('global flag does not expose a non-pilot company', async ({page}) => {
  await installRoutes(page, {
    readiness: {
      ...readyPayload,
      enabled: false,
      visible: false,
      generation_allowed: false,
      rollout: {...readyPayload.rollout, pilot_company: false, active: false},
    },
  });
  await page.goto('/');
  await injectTrainingOutput(page);
  await page.waitForTimeout(450);
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

test('approval dialog distinguishes application approval and qualified PAdES', async ({page}) => {
  const calls = await installRoutes(page, {initialRows: [generatedVersion()]});
  await page.goto('/');
  await injectTrainingOutput(page);

  const panel = page.locator('.training-presentation-panel');
  await expect(panel.getByText('Sunumu Onayla')).toBeVisible();
  await panel.getByText('Sunumu Onayla').click();

  const dialog = page.locator('.training-presentation-approval-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('nitelikli elektronik imza yerine geçmez')).toBeVisible();
  const method = dialog.locator('[name="approval_method"]');
  await method.selectOption('qualified_esign');
  await expect(dialog.locator('[name="esign_request_id"]')).toBeVisible();
  await expect(dialog.getByText('PDF hash eşleşmesi')).toBeVisible();
  await method.selectOption('application_approval');
  await expect(dialog.locator('[name="esign_request_id"]')).toBeHidden();
  await dialog.locator('[name="approval_note"]').fill('Pilot uzman incelemesi tamamlandı.');
  await dialog.getByText("Hash'leri Kilitle ve Onayla").click();

  await expect(dialog).toHaveCount(0);
  await expect(panel.locator('.training-presentation-panel__approval strong').getByText('Uygulama içi uzman onayı', {exact: true})).toBeVisible();
  await expect(panel.getByText('Onaylı Sürümü Arşivle')).toBeVisible();
  expect(calls.approvalBody()).toEqual({
    approval_method: 'application_approval',
    confirmed_manifest_hash: 'a'.repeat(64),
    approval_note: 'Pilot uzman incelemesi tamamlandı.',
    esign_request_id: null,
  });
});

for (const viewport of [
  {name: 'desktop', width: 1440, height: 900},
  {name: 'laptop', width: 1024, height: 768},
  {name: 'tablet', width: 768, height: 1024},
  {name: 'mobile', width: 390, height: 844},
]) {
  test(`${viewport.name} panel and approval dialog do not overflow horizontally`, async ({page}) => {
    await page.setViewportSize({width: viewport.width, height: viewport.height});
    await installRoutes(page, {initialRows: [generatedVersion()]});
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

    await panel.getByText('Sunumu Onayla').click();
    const dialog = page.locator('.training-presentation-approval-dialog__card');
    await expect(dialog).toBeVisible();
    const dialogBox = await dialog.boundingBox();
    expect(dialogBox).not.toBeNull();
    expect(dialogBox.x).toBeGreaterThanOrEqual(0);
    expect(dialogBox.x + dialogBox.width).toBeLessThanOrEqual(viewport.width);
    expect(dialogBox.y).toBeGreaterThanOrEqual(0);
    expect(dialogBox.y + dialogBox.height).toBeLessThanOrEqual(viewport.height);
  });
}
