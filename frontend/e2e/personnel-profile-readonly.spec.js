import {test, expect} from '@playwright/test';

const readyPayload = {
  readiness_version: 'personnel-profile-readiness-v1',
  company_id: 35,
  enabled: true,
  visible: true,
  read_only: true,
  rollout: {
    global_enabled: true,
    force_off: false,
    allowlist_configured: true,
    pilot_company: true,
    active: true,
  },
  capabilities: {
    employee_summary: true,
    professional_summary: true,
    profile_record_management: false,
    file_upload: false,
    cv_generation: false,
    external_sharing: false,
    restricted_data: false,
  },
};

const employeeSummary = {
  summary_version: 'personnel-profile-summary-v1',
  subject: {type: 'employee', id: 41},
  scope: {company_id: 35, company_name: 'Test İşyerim', branch_id: null, branch_name: null},
  profile: {
    full_name: 'Ayşe Yılmaz',
    national_identity_masked: '123******90',
    job_title: 'Kaynakçı',
    department: 'Üretim',
    employment_start_date: '2024-01-15',
    employment_status: 'active',
  },
  privacy: {
    data_minimized: true,
    national_identity_full_included: false,
    special_status_included: false,
    health_data_included: false,
    criminal_record_included: false,
    restricted_documents_included: false,
  },
};

const professionalSummary = {
  summary_version: 'personnel-profile-summary-v1',
  subject: {type: 'professional', id: 7},
  scope: {osgb_id: 4, company_id: 35, company_name: 'Test İşyerim'},
  profile: {
    full_name: 'Mehmet Uzman',
    professional_type: 'safety_specialist',
    email: 'uzman@example.test',
    phone: '+90 555 000 00 00',
    certificate_class: 'A',
    certificate_number: 'UZM-123',
    certificate_date: '2020-05-01',
    employment_status: 'active',
    active_assignment_count: 2,
  },
  privacy: {
    data_minimized: true,
    national_identity_full_included: false,
    special_status_included: false,
    health_data_included: false,
    criminal_record_included: false,
    restricted_documents_included: false,
  },
};

async function installCommonRoutes(page, readinessPayload = readyPayload) {
  let readinessCalls = 0;
  await page.route('**/health', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: '{"ok":true}'});
  });
  await page.route('**/api/v1/personnel-profiles/readiness?company_id=35', async (route) => {
    readinessCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(readinessPayload),
    });
  });
  return {readinessCalls: () => readinessCalls};
}

async function injectEmployeePage(page) {
  await page.evaluate(() => {
    document.body.innerHTML = `
      <main style="width:100%;max-width:100%;padding:16px">
        <div class="page-title"><h3>Personel Yönetimi</h3></div>
        <label class="field"><span>İşyeri</span><select><option value="35" selected>Test İşyerim</option></select></label>
        <section class="panel"><button type="button">Personel Ekle</button><p>Mevcut personel listesi korunur.</p></section>
      </main>`;
  });
}

async function injectProfessionalPage(page) {
  await page.evaluate(() => {
    document.body.innerHTML = `
      <main style="width:100%;max-width:100%;padding:16px">
        <div class="page-title"><h3>İSG Profesyonelleri</h3></div>
        <label class="field"><span>OSGB</span><select><option value="4" selected>Test OSGB</option></select></label>
        <section class="panel"><button type="button">Yeni Profesyonel</button></section>
      </main>`;
  });
}

test('flag disabled leaves the existing personnel page unchanged', async ({page}) => {
  await installCommonRoutes(page, {
    ...readyPayload,
    enabled: false,
    visible: false,
    rollout: {...readyPayload.rollout, global_enabled: false, active: false},
  });
  await page.goto('/');
  await injectEmployeePage(page);
  await page.waitForTimeout(450);

  await expect(page.locator('.personnel-profile-readonly-entry')).toHaveCount(0);
  await expect(page.getByText('Personel Ekle')).toBeVisible();
  await expect(page.getByText('Mevcut personel listesi korunur.')).toBeVisible();
});

test('employee pilot preview shows only the privacy-minimized summary', async ({page}) => {
  const calls = await installCommonRoutes(page);
  await page.route('**/api/v1/employees?company_id=35&include_inactive=true', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{
        id: 41,
        full_name: 'Ayşe Yılmaz',
        national_id_masked: '12345678990',
        job_title: 'Kaynakçı',
        department: 'Üretim',
        special_status: 'Engelli/Hükümlü',
        is_active: true,
      }]),
    });
  });
  await page.route('**/api/v1/personnel-profiles/employee/41/summary', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(employeeSummary)});
  });

  await page.goto('/');
  await injectEmployeePage(page);

  const entry = page.locator('.personnel-profile-readonly-entry');
  await expect(entry).toBeVisible();
  await expect(entry.getByText('Personel Kartlarını Görüntüle')).toBeVisible();
  await expect(page.getByText('Personel Ekle')).toBeVisible();
  expect(calls.readinessCalls()).toBeLessThanOrEqual(1);

  await entry.getByText('Personel Kartlarını Görüntüle').click();
  const dialog = page.locator('.personnel-profile-readonly-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Ayşe Yılmaz')).toBeVisible();
  await expect(dialog.getByText('123******90')).toBeVisible();
  await expect(dialog.getByText('Veri minimizasyonu etkin')).toBeVisible();
  await expect(dialog.getByText('Sağlık, adli sicil, özel durum')).toBeVisible();

  const html = await dialog.innerHTML();
  expect(html).not.toContain('12345678990');
  expect(html).not.toContain('Engelli/Hükümlü');
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
});

test('professional preview is built only from an active pilot assignment', async ({page}) => {
  await installCommonRoutes(page);
  await page.route('**/api/v1/osgb/professionals?osgb_id=4', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {id: 7, full_name: 'Mehmet Uzman', professional_type: 'safety_specialist', certificate_class: 'A', is_active: true},
        {id: 8, full_name: 'Atamasız Hekim', professional_type: 'workplace_physician', is_active: true},
      ]),
    });
  });
  await page.route('**/api/v1/osgb/assignments?osgb_id=4', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {professional_id: 7, company_id: 35, status: 'active'},
        {professional_id: 8, company_id: 35, status: 'ended'},
      ]),
    });
  });
  await page.route('**/api/v1/personnel-profiles/professional/7/summary?company_id=35', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(professionalSummary)});
  });

  await page.goto('/');
  await injectProfessionalPage(page);

  const entry = page.locator('.personnel-profile-readonly-entry');
  await expect(entry).toBeVisible();
  await entry.getByText('Profesyonel Profilleri Görüntüle').click();
  const dialog = page.locator('.personnel-profile-readonly-dialog');
  await expect(dialog.getByText('Mehmet Uzman')).toBeVisible();
  await expect(dialog.getByText('İş Güvenliği Uzmanı')).toBeVisible();
  await expect(dialog.getByText('UZM-123')).toBeVisible();
  await expect(dialog.getByText('Atamasız Hekim')).toHaveCount(0);
});

for (const viewport of [
  {name: 'desktop', width: 1440, height: 900},
  {name: 'tablet', width: 768, height: 1024},
  {name: 'mobile', width: 390, height: 844},
]) {
  test(`${viewport.name} read-only profile dialog does not overflow horizontally`, async ({page}) => {
    await page.setViewportSize({width: viewport.width, height: viewport.height});
    await installCommonRoutes(page);
    await page.route('**/api/v1/employees?company_id=35&include_inactive=true', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{id: 41, full_name: 'Ayşe Yılmaz', job_title: 'Kaynakçı', is_active: true}]),
      });
    });
    await page.route('**/api/v1/personnel-profiles/employee/41/summary', async (route) => {
      await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(employeeSummary)});
    });

    await page.goto('/');
    await injectEmployeePage(page);
    await page.locator('.personnel-profile-readonly-entry__button').click();
    const dialog = page.locator('.personnel-profile-readonly-dialog__card');
    await expect(dialog).toBeVisible();

    const dimensions = await page.evaluate(() => ({
      viewport: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      card: document.querySelector('.personnel-profile-readonly-dialog__card')?.getBoundingClientRect(),
      controls: [...document.querySelectorAll('.personnel-profile-readonly-dialog button')].map((button) => ({
        width: button.getBoundingClientRect().width,
        height: button.getBoundingClientRect().height,
      })),
    }));
    expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewport);
    expect(dimensions.card.x).toBeGreaterThanOrEqual(0);
    expect(dimensions.card.x + dimensions.card.width).toBeLessThanOrEqual(viewport.width);
    for (const control of dimensions.controls) {
      expect(control.height).toBeGreaterThanOrEqual(44);
    }
  });
}
