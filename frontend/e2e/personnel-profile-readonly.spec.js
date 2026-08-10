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
    profile_record_management: true,
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
  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({id: 2, full_name: 'OSGB Yönetici', role: 'company_admin', osgb_id: 4}),
    });
  });
  await page.route('**/api/v1/osgb', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify([{id: 4, name: 'Test OSGB'}])});
  });
  await page.route('**/api/v1/companies', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify([{id: 35, name: 'Test İşyerim'}])});
  });
  await page.route('**/api/v1/personnel-profiles/readiness?company_id=35', async (route) => {
    readinessCalls += 1;
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(readinessPayload)});
  });
  return {readinessCalls: () => readinessCalls};
}

async function installEmployeeRoutes(page) {
  await page.route('**/api/v1/osgb/professionals?osgb_id=4', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: '[]'});
  });
  await page.route('**/api/v1/osgb/assignments?osgb_id=4', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: '[]'});
  });
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
  await expect(page.locator('[data-personnel-profile-manager="true"]')).toHaveCount(0);
  await expect(page.getByText('Personel Ekle')).toBeVisible();
  await expect(page.getByText('Mevcut personel listesi korunur.')).toBeVisible();
});

test('employee entry opens the full privacy-minimized management workspace', async ({page}) => {
  const calls = await installCommonRoutes(page);
  await installEmployeeRoutes(page);
  await page.goto('/');
  await injectEmployeePage(page);

  const entry = page.locator('.personnel-profile-readonly-entry');
  await expect(entry).toBeVisible();
  await expect(entry.getByText('Personel Kartlarını Görüntüle')).toBeVisible();
  await expect(page.getByText('Personel Ekle')).toBeVisible();
  expect(calls.readinessCalls()).toBeLessThanOrEqual(1);

  await entry.getByText('Personel Kartlarını Görüntüle').click();
  const manager = page.locator('[data-personnel-profile-manager="true"]');
  await expect(manager).toBeVisible();
  await expect(manager.getByRole('heading', {name: 'Dijital Personel Kartları'})).toBeVisible();
  await expect(manager.getByRole('heading', {name: 'Ayşe Yılmaz'})).toBeVisible();
  await expect(manager.getByText('123******90', {exact: true})).toBeVisible();
  await expect(manager.getByText('Standart profesyonel veriler', {exact: true})).toBeVisible();
  await expect(page.locator('.personnel-profile-readonly-dialog')).toHaveCount(0);

  const html = await manager.innerHTML();
  expect(html).not.toContain('12345678990');
  expect(html).not.toContain('Engelli/Hükümlü');
  await page.keyboard.press('Escape');
  await expect(manager).toHaveCount(0);
  await expect(page.getByText('Personel Ekle')).toBeVisible();
});

test('professional workspace is built only from an active pilot assignment', async ({page}) => {
  await installCommonRoutes(page);
  await page.route('**/api/v1/employees?company_id=35&include_inactive=true', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: '[]'});
  });
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
        {id: 71, professional_id: 7, company_id: 35, professional_type: 'safety_specialist', start_date: '2025-01-01', status: 'active'},
        {id: 72, professional_id: 8, company_id: 35, professional_type: 'workplace_physician', start_date: '2025-01-01', status: 'ended'},
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
  const manager = page.locator('[data-personnel-profile-manager="true"]');
  await expect(manager.getByRole('heading', {name: 'Mehmet Uzman'})).toBeVisible();
  await expect(manager.getByText('İş Güvenliği Uzmanı', {exact: true}).first()).toBeVisible();
  await expect(manager.getByText('UZM-123', {exact: true})).toBeVisible();
  await expect(manager.getByText('Atamasız Hekim')).toHaveCount(0);
});

for (const viewport of [
  {name: 'desktop', width: 1440, height: 900},
  {name: 'tablet', width: 768, height: 1024},
  {name: 'mobile', width: 390, height: 844},
]) {
  test(`${viewport.name} full personnel workspace does not overflow horizontally`, async ({page}) => {
    await page.setViewportSize({width: viewport.width, height: viewport.height});
    await installCommonRoutes(page);
    await installEmployeeRoutes(page);
    await page.goto('/');
    await injectEmployeePage(page);
    await page.locator('.personnel-profile-readonly-entry__button').click();

    const manager = page.locator('[data-personnel-profile-manager="true"]');
    await expect(manager).toBeVisible();
    await expect(manager.getByRole('heading', {name: 'Dijital Personel Kartları'})).toBeVisible();
    const dimensions = await manager.evaluate((element) => ({
      viewport: window.innerWidth,
      hostWidth: element.getBoundingClientRect().width,
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      documentWidth: document.documentElement.scrollWidth,
      controls: [...element.querySelectorAll('button')]
        .filter((button) => button.getClientRects().length > 0)
        .map((button) => ({height: button.getBoundingClientRect().height})),
    }));
    expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewport);
    expect(dimensions.hostWidth).toBeLessThanOrEqual(viewport.width + 1);
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
    for (const control of dimensions.controls) {
      expect(control.height).toBeGreaterThanOrEqual(40);
    }
  });
}
