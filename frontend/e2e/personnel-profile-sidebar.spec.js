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
    active_assignment_count: 1,
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

async function installRoutes(page, readinessPayload = readyPayload) {
  await page.route('**/health', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: '{"ok":true}'});
  });
  await page.route('**/api/v1/osgb', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify([{id: 4, name: 'Test OSGB'}])});
  });
  await page.route('**/api/v1/companies', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify([{id: 35, name: 'Test İşyerim'}])});
  });
  await page.route('**/api/v1/osgb/professionals?osgb_id=4', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{
        id: 7,
        full_name: 'Mehmet Uzman',
        professional_type: 'safety_specialist',
        certificate_class: 'A',
        is_active: true,
      }]),
    });
  });
  await page.route('**/api/v1/osgb/assignments?osgb_id=4', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{professional_id: 7, company_id: 35, osgb_id: 4, status: 'active'}]),
    });
  });
  await page.route('**/api/v1/personnel-profiles/readiness?company_id=35', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(readinessPayload)});
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
  await page.route('**/api/v1/personnel-profiles/professional/7/summary?company_id=35', async (route) => {
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(professionalSummary)});
  });
}

async function injectDesktopShell(page) {
  await page.evaluate(() => {
    document.body.innerHTML = `
      <div class="app-shell">
        <aside>
          <nav class="nav-desktop">
            <button type="button" data-nav="osgb_dashboard"><span>OSGB Ana Panel</span></button>
            <button type="button" data-nav="companies"><span>İşyerleri</span></button>
            <button type="button" data-nav="professionals"><span>İSG Profesyonelleri</span></button>
            <button type="button" data-nav="assignments"><span>Görevlendirmeler</span></button>
          </nav>
        </aside>
        <section class="workspace"><main><h3>OSGB Ana Panel</h3></main></section>
      </div>`;
  });
}

async function injectMobileSheet(page) {
  await page.evaluate(() => {
    document.body.innerHTML = `
      <div class="mobile-nav-sheet">
        <div class="mobile-nav-sheet-head"><strong>Modüller</strong><button type="button">Kapat</button></div>
        <div class="mobile-nav-sheet-grid">
          <button type="button"><span>OSGB Ana Panel</span></button>
          <button type="button"><span>İşyerleri</span></button>
          <button type="button"><span>İSG Profesyonelleri</span></button>
          <button type="button"><span>Görevlendirmeler</span></button>
        </div>
      </div>`;
  });
}

test('feature disabled preserves the existing OSGB navigation exactly', async ({page}) => {
  await installRoutes(page, {
    ...readyPayload,
    enabled: false,
    visible: false,
    rollout: {...readyPayload.rollout, global_enabled: false, active: false},
  });
  await page.goto('/');
  await injectDesktopShell(page);
  await page.waitForTimeout(500);

  await expect(page.locator('[data-personnel-profile-nav]')).toHaveCount(0);
  await expect(page.locator('.nav-desktop > button')).toHaveCount(4);
  await expect(page.locator('button[data-nav="professionals"]')).toBeVisible();
  await expect(page.locator('button[data-nav="assignments"]')).toBeVisible();
});

test('pilot sidebar entry is inserted once after İSG Profesyonelleri', async ({page}) => {
  await installRoutes(page);
  await page.goto('/');
  await injectDesktopShell(page);

  const entry = page.locator('[data-personnel-profile-nav="desktop"]');
  await expect(entry).toBeVisible();
  await expect(entry).toContainText('Dijital Personel Kartı');

  const order = await page.evaluate(() => {
    const button = document.querySelector('[data-personnel-profile-nav="desktop"]');
    return {
      previous: button?.previousElementSibling?.getAttribute('data-nav'),
      count: document.querySelectorAll('[data-personnel-profile-nav="desktop"]').length,
    };
  });
  expect(order).toEqual({previous: 'professionals', count: 1});

  await page.evaluate(() => document.body.appendChild(document.createElement('span')));
  await page.waitForTimeout(350);
  await expect(page.locator('[data-personnel-profile-nav="desktop"]')).toHaveCount(1);
});

test('sidebar entry opens combined privacy-minimized employee and professional cards', async ({page}) => {
  await installRoutes(page);
  await page.goto('/');
  await injectDesktopShell(page);

  await page.locator('[data-personnel-profile-nav="desktop"]').click();
  const dialog = page.locator('.personnel-profile-readonly-dialog');
  const list = dialog.locator('.personnel-profile-readonly-dialog__list');
  const detail = dialog.locator('.personnel-profile-readonly-dialog__detail');
  await expect(dialog).toBeVisible();
  await expect(list.getByText('Ayşe Yılmaz', {exact: true})).toBeVisible();
  await expect(list.getByText('Mehmet Uzman', {exact: true})).toBeVisible();

  await expect(detail.getByRole('heading', {name: 'Ayşe Yılmaz'})).toBeVisible();
  await expect(detail.getByText('123******90', {exact: true})).toBeVisible();

  await list.getByText('Mehmet Uzman', {exact: true}).click();
  await expect(detail.getByRole('heading', {name: 'Mehmet Uzman'})).toBeVisible();
  await expect(detail.getByText('UZM-123', {exact: true})).toBeVisible();

  const html = await dialog.innerHTML();
  expect(html).not.toContain('12345678990');
  expect(html).not.toContain('Engelli/Hükümlü');
});

test('pilot entry is available in the mobile all-modules sheet without duplicates', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await installRoutes(page);
  await page.goto('/');
  await injectMobileSheet(page);

  const entry = page.locator('[data-personnel-profile-nav="mobile"]');
  await expect(entry).toBeVisible();
  await expect(entry).toContainText('Dijital Personel Kartı');
  const result = await page.evaluate(() => {
    const button = document.querySelector('[data-personnel-profile-nav="mobile"]');
    return {
      previous: button?.previousElementSibling?.textContent?.trim(),
      count: document.querySelectorAll('[data-personnel-profile-nav="mobile"]').length,
      documentWidth: document.documentElement.scrollWidth,
      viewport: window.innerWidth,
    };
  });
  expect(result.previous).toContain('İSG Profesyonelleri');
  expect(result.count).toBe(1);
  expect(result.documentWidth).toBeLessThanOrEqual(result.viewport);
});
