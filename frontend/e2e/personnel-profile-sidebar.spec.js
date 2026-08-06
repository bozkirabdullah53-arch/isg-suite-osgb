import {test, expect} from '@playwright/test';

const readyPayload = {
  readiness_version: 'osgb-professional-card-v1',
  osgb_id: 4,
  enabled: true,
  visible: true,
  scope: 'osgb_professionals_only',
  employee_records_included: false,
  assignment_required_for_visibility: false,
  rollout: {
    global_enabled: true,
    force_off: false,
    allowlist_configured: true,
    pilot_osgb: true,
    active: true,
  },
};

const professionals = [
  {
    id: 7,
    osgb_id: 4,
    full_name: 'Mehmet Uzman',
    professional_type: 'safety_specialist',
    certificate_class: 'A',
    certificate_number: 'UZM-123',
    is_active: true,
  },
  {
    id: 8,
    osgb_id: 4,
    full_name: 'Gönül Hekim',
    professional_type: 'workplace_physician',
    certificate_number: 'HEK-456',
    is_active: true,
  },
  {
    id: 9,
    osgb_id: 4,
    full_name: 'Deniz DSP',
    professional_type: 'other_health_personnel',
    certificate_number: 'DSP-789',
    is_active: true,
  },
  // Even a malformed workplace-shaped row must not enter the OSGB card list.
  {
    id: 41,
    company_id: 35,
    full_name: 'Ayşe Yılmaz',
    job_title: 'Kaynakçı',
    is_active: true,
  },
];

function professionalSummary(id) {
  const professional = professionals.find((row) => Number(row.id) === Number(id));
  return {
    summary_version: 'osgb-professional-profile-summary-v1',
    subject: {type: 'professional', id: Number(id)},
    scope: {osgb_id: 4, company_id: null, company_name: null},
    profile: {
      full_name: professional?.full_name || 'OSGB Profesyoneli',
      professional_type: professional?.professional_type || 'safety_specialist',
      email: 'professional@example.com',
      phone: '+90 555 000 00 00',
      certificate_class: professional?.certificate_class || null,
      certificate_number: professional?.certificate_number || null,
      certificate_date: '2020-05-01',
      employment_status: 'active',
      // Gönül Hekim deliberately has no workplace assignment.
      active_assignment_count: Number(id) === 8 ? 0 : 1,
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
}

const emptySnapshot = {
  profile: {
    id: 55,
    osgb_id: 4,
    company_id: null,
    branch_id: null,
    subject_type: 'professional',
    employee_id: null,
    professional_id: 7,
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
  let employeeRequestCount = 0;
  const json = (route, body, status = 200) => route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });

  await page.route('**/health', (route) => json(route, {ok: true}));
  await page.route('**/api/v1/auth/me', (route) => json(route, {
    id: 2,
    full_name: 'OSGB Yönetici',
    role: 'company_admin',
    osgb_id: 4,
  }));
  await page.route('**/api/v1/osgb', (route) => json(route, [{id: 4, name: 'Test OSGB'}]));
  await page.route('**/api/v1/osgb-personnel-profiles/readiness?osgb_id=4', (route) => json(route, readinessPayload));
  await page.route('**/api/v1/osgb-personnel-profiles/professionals?osgb_id=4', (route) => json(route, {items: professionals}));
  await page.route('**/api/v1/osgb/assignments?osgb_id=4', (route) => json(route, [
    {id: 70, professional_id: 7, company_id: 35, osgb_id: 4, start_date: '2025-01-01', status: 'active'},
  ]));

  await page.route(/\/api\/v1\/employees(?:\?|$)/, async (route) => {
    employeeRequestCount += 1;
    await json(route, {detail: 'OSGB kart ekranı işyeri çalışanı sorgulayamaz.'}, 500);
  });
  await page.route(/\/api\/v1\/personnel-profiles\/employee\//, async (route) => {
    employeeRequestCount += 1;
    await json(route, {detail: 'OSGB kart ekranı employee summary kullanamaz.'}, 500);
  });

  await page.route(/\/api\/v1\/osgb-personnel-profiles\/professional\/(\d+)\/summary$/, async (route) => {
    const match = new URL(route.request().url()).pathname.match(/professional\/(\d+)\/summary$/);
    await json(route, professionalSummary(Number(match?.[1] || 0)));
  });
  await page.route(/\/api\/v1\/osgb-personnel-profiles\/professionals\/(\d+)$/, async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    const match = new URL(route.request().url()).pathname.match(/professionals\/(\d+)$/);
    snapshot.profile.professional_id = Number(match?.[1] || 7);
    await json(route, {created: true, profile: snapshot.profile, privacy: snapshot.privacy});
  });
  await page.route('**/api/v1/osgb-personnel-profiles/55', (route) => json(route, snapshot));
  await page.route('**/api/v1/osgb-personnel-profiles/55/contacts', async (route) => {
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
    await json(route, {
      created: true,
      id: 91,
      entry_key: snapshot.contacts[0].entry_key,
      version: 1,
      verification_status: 'unverified',
      lifecycle_status: 'active',
    });
  });

  return {employeeRequestCount: () => employeeRequestCount};
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
});

test('OSGB-only sidebar entry is inserted once after İSG Profesyonelleri', async ({page}) => {
  const requests = await installRoutes(page);
  await page.goto('/');
  await injectDesktopShell(page);
  const entry = page.locator('[data-personnel-profile-nav="desktop"]');
  await expect(entry).toBeVisible();
  await expect(entry).toContainText('Dijital Profesyonel Kartları');
  const order = await page.evaluate(() => {
    const button = document.querySelector('[data-personnel-profile-nav="desktop"]');
    return {
      previous: button?.previousElementSibling?.getAttribute('data-nav'),
      count: document.querySelectorAll('[data-personnel-profile-nav="desktop"]').length,
    };
  });
  expect(order).toEqual({previous: 'professionals', count: 1});
  expect(requests.employeeRequestCount()).toBe(0);
});

test('manager shows only own OSGB professionals and persists a professional contact version', async ({page}) => {
  const requests = await installRoutes(page);
  await page.goto('/');
  await injectDesktopShell(page);
  await page.locator('[data-personnel-profile-nav="desktop"]').click();

  const manager = page.locator('[data-personnel-profile-manager="true"]');
  await expect(manager).toBeVisible();
  await expect(manager.getByRole('heading', {name: 'Dijital Personel Kartları'})).toBeVisible();
  await expect(manager.getByText('Mehmet Uzman', {exact: true}).first()).toBeVisible();
  await expect(manager.getByText('Gönül Hekim', {exact: true}).first()).toBeVisible();
  await expect(manager.getByText('Deniz DSP', {exact: true}).first()).toBeVisible();
  await expect(manager.getByText('Ayşe Yılmaz', {exact: true})).toHaveCount(0);
  await expect(manager.getByText('Kaynakçı', {exact: true})).toHaveCount(0);
  expect(requests.employeeRequestCount()).toBe(0);

  await manager.getByText('Mehmet Uzman', {exact: true}).first().click();
  await expect(manager.getByText('OSGB Profesyonel Dijital Kartı', {exact: true})).toBeVisible();
  await manager.getByRole('button', {name: /Kartı başlat/}).click();
  await expect(manager.getByText('Profil #55', {exact: true})).toBeVisible();
  await manager.getByRole('button', {name: 'İletişim'}).click();
  await manager.getByLabel('Etiket').fill('Kurumsal');
  await manager.getByLabel('İletişim bilgisi').fill('mehmet@example.com');
  await manager.getByRole('button', {name: 'Ekle'}).click();
  await expect(manager.getByText('mehmet@example.com', {exact: true})).toBeVisible();
  await expect(manager.getByText(/İletişim bilgisi eklendi/)).toBeVisible();
  expect(requests.employeeRequestCount()).toBe(0);
});

test('atamasız OSGB hekimi kart listesinde kalır', async ({page}) => {
  await installRoutes(page);
  await page.goto('/');
  await injectDesktopShell(page);
  await page.locator('[data-personnel-profile-nav="desktop"]').click();
  const manager = page.locator('[data-personnel-profile-manager="true"]');
  await manager.getByText('Gönül Hekim', {exact: true}).first().click();
  await expect(manager.getByText('Aktif görevlendirme', {exact: true})).toBeVisible();
  await expect(manager.getByText('0', {exact: true}).first()).toBeVisible();
});

test('OSGB-only entry and manager remain usable without mobile overflow', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await installRoutes(page);
  await page.goto('/');
  await injectMobileSheet(page);
  const entry = page.locator('[data-personnel-profile-nav="mobile"]');
  await expect(entry).toBeVisible();
  await expect(entry).toContainText('Dijital Profesyonel Kartları');
  await entry.click();
  const manager = page.locator('[data-personnel-profile-manager="true"]');
  await expect(manager).toBeVisible();
  const dimensions = await manager.evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
  await expect(manager.getByRole('button', {name: /Önceki ekrana dön/})).toBeVisible();
});
