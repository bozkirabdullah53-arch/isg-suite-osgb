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

const emptySnapshot = {
  profile: {
    id: 55,
    osgb_id: 4,
    company_id: 35,
    branch_id: null,
    subject_type: 'employee',
    employee_id: 41,
    professional_id: null,
    user_id: null,
    status: 'active',
    created_at: '2026-08-06T12:00:00',
    archived_at: null,
  },
  contacts: [],
  competencies: [],
  experiences: [],
  privacy: {
    ordinary_professional_data_only: true,
    national_identity_included: false,
    home_address_included: false,
    emergency_contact_included: false,
    health_data_included: false,
    criminal_record_included: false,
    salary_included: false,
    disciplinary_data_included: false,
    documents_included: false,
    external_sharing_enabled: false,
  },
};

async function installRoutes(page, readinessPayload = readyPayload) {
  let snapshot = structuredClone(emptySnapshot);
  await page.route('**/health', async (route) => route.fulfill({status: 200, contentType: 'application/json', body: '{"ok":true}'}));
  await page.route('**/api/v1/auth/me', async (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({id: 2, full_name: 'OSGB Yönetici', role: 'company_admin', osgb_id: 4})}));
  await page.route('**/api/v1/osgb', async (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify([{id: 4, name: 'Test OSGB'}])}));
  await page.route('**/api/v1/companies', async (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify([{id: 35, name: 'Test İşyerim'}])}));
  await page.route('**/api/v1/osgb/professionals?osgb_id=4', async (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify([{id: 7, full_name: 'Mehmet Uzman', professional_type: 'safety_specialist', certificate_class: 'A', is_active: true}])}));
  await page.route('**/api/v1/osgb/assignments?osgb_id=4', async (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify([{id: 70, professional_id: 7, company_id: 35, osgb_id: 4, professional_type: 'safety_specialist', start_date: '2025-01-01', status: 'active'}])}));
  await page.route('**/api/v1/personnel-profiles/readiness?company_id=35', async (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(readinessPayload)}));
  await page.route('**/api/v1/employees?company_id=35&include_inactive=true', async (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify([{id: 41, full_name: 'Ayşe Yılmaz', national_id_masked: '12345678990', job_title: 'Kaynakçı', department: 'Üretim', special_status: 'Engelli/Hükümlü', is_active: true}])}));
  await page.route('**/api/v1/personnel-profiles/employee/41/summary', async (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(employeeSummary)}));
  await page.route('**/api/v1/personnel-profiles/professional/7/summary?company_id=35', async (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(professionalSummary)}));
  await page.route('**/api/v1/personnel-profiles/55', async (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(snapshot)}));
  await page.route('**/api/v1/personnel-profiles', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({created: true, profile: emptySnapshot.profile, privacy: emptySnapshot.privacy})});
  });
  await page.route('**/api/v1/personnel-profiles/55/contacts', async (route) => {
    const body = route.request().postDataJSON();
    snapshot = {
      ...snapshot,
      contacts: [{
        id: 91,
        entry_key: 'c8384df3-c5e0-4ef7-98ee-a9b36efe04af',
        version: 1,
        contact_type: body.contact_type,
        label: body.label,
        contact_value: body.contact_value,
        is_primary: Boolean(body.is_primary),
        visibility: body.visibility,
        verification_status: 'unverified',
        lifecycle_status: 'active',
        created_at: '2026-08-06T12:05:00',
      }],
    };
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({created: true, id: 91, entry_key: snapshot.contacts[0].entry_key, version: 1, verification_status: 'unverified', lifecycle_status: 'active'})});
  });
}

async function injectDesktopShell(page) {
  await page.evaluate(() => {
    document.body.innerHTML = `
      <div class="app-shell">
        <aside><nav class="nav-desktop">
          <button type="button" data-nav="osgb_dashboard"><span>OSGB Ana Panel</span></button>
          <button type="button" data-nav="companies"><span>İşyerleri</span></button>
          <button type="button" data-nav="professionals"><span>İSG Profesyonelleri</span></button>
          <button type="button" data-nav="assignments"><span>Görevlendirmeler</span></button>
        </nav></aside>
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
  await installRoutes(page, {...readyPayload, enabled: false, visible: false, rollout: {...readyPayload.rollout, global_enabled: false, active: false}});
  await page.goto('/');
  await injectDesktopShell(page);
  await page.waitForTimeout(500);
  await expect(page.locator('[data-personnel-profile-nav]')).toHaveCount(0);
  await expect(page.locator('.nav-desktop > button')).toHaveCount(4);
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
    return {previous: button?.previousElementSibling?.getAttribute('data-nav'), count: document.querySelectorAll('[data-personnel-profile-nav="desktop"]').length};
  });
  expect(order).toEqual({previous: 'professionals', count: 1});
});

test('sidebar opens full workspace manager and persists a real contact version', async ({page}) => {
  await installRoutes(page);
  await page.goto('/');
  await injectDesktopShell(page);
  await page.locator('[data-personnel-profile-nav="desktop"]').click();

  const manager = page.locator('[data-personnel-profile-manager="true"]');
  await expect(manager).toBeVisible();
  await expect(manager.getByRole('heading', {name: 'Dijital Personel Kartları'})).toBeVisible();
  await expect(manager.getByText('Ayşe Yılmaz', {exact: true}).first()).toBeVisible();
  await expect(manager.getByText('Mehmet Uzman', {exact: true}).first()).toBeVisible();
  await expect(page.locator('.personnel-profile-readonly-dialog')).toHaveCount(0);
  await expect(manager.getByText('123******90', {exact: true})).toBeVisible();
  expect(await manager.innerHTML()).not.toContain('12345678990');
  expect(await manager.innerHTML()).not.toContain('Engelli/Hükümlü');

  await manager.getByRole('button', {name: /Kartı başlat/}).click();
  await expect(manager.getByText('Profil #55', {exact: true})).toBeVisible();
  await manager.getByRole('button', {name: 'İletişim'}).click();
  await manager.getByLabel('Etiket').fill('Kurumsal');
  await manager.getByLabel('İletişim bilgisi').fill('ayse@example.test');
  await manager.getByRole('button', {name: 'Ekle'}).click();
  await expect(manager.getByText('ayse@example.test', {exact: true})).toBeVisible();
  await expect(manager.getByText(/İletişim bilgisi eklendi/)).toBeVisible();
});

test('pilot entry and full manager remain usable without mobile overflow', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await installRoutes(page);
  await page.goto('/');
  await injectMobileSheet(page);
  const entry = page.locator('[data-personnel-profile-nav="mobile"]');
  await expect(entry).toBeVisible();
  await entry.click();
  const manager = page.locator('[data-personnel-profile-manager="true"]');
  await expect(manager).toBeVisible();
  const dimensions = await manager.evaluate((element) => ({scrollWidth: element.scrollWidth, clientWidth: element.clientWidth}));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
  await expect(manager.getByRole('button', {name: /Önceki ekrana dön/})).toBeVisible();
});
