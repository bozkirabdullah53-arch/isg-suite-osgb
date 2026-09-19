import {test, expect} from '@playwright/test';

const company = {id: 42, name: 'ÖRNEK AKÜ VE OTOMOTİV SAN. TİC. LTD. ŞTİ.', is_active: true};
const counts = {employees: 24, ppe: 620, sds: 12, periodic: 18, measurements: 9, nearMiss: 4, accidents: 1, capa: 8};
const modules = [
  ['employees', /Personel/], ['ppe', /KKD/], ['sds', /SDS/],
  ['periyodik_kontrol', /Periyodik/], ['ortam_olcum', /Ortam/],
  ['near_miss', /Ramak/], ['accident', /Kaz/], ['capa', /DÖF Yönetimi/],
  ['isg_kurulu', /İSG Kurulu/],
];

async function setup(page, {
  email = 'isyeri.42@kiosk.isgsuite.tr',
  summaryError = false,
  committeeCandidates = {mandatory: [], other: [], missing_mandatory: []},
  employees = [],
  healthRows = [],
} = {}) {
  const errors = [];
  let qrRequests = 0;
  let employeeRows = [...employees];
  const bulkPurgePayloads = [];
  let employeeTemplateRequests = 0;
  const employeeImportRequests = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.addInitScript(() => {
    const payload = btoa(JSON.stringify({sub: '9', exp: Math.floor(Date.now() / 1000) + 3600}));
    sessionStorage.setItem('isg_token', `e30.${payload}.fixture`);
    localStorage.setItem('isg_pwa_shortcut_choice_v1', 'dismissed');
  });
  const json = (route, body, status = 200) => route.fulfill({
    status, contentType: 'application/json', body: JSON.stringify(body),
    headers: {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'},
  });
  await page.route('**/health', (route) => json(route, {status: 'ok'}));
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace('/api/v1', '').replace(/\/$/, '');
    if (request.method() === 'OPTIONS') return json(route, {});
    if (path === '/auth/me') return json(route, {
      id: 9, email, full_name: 'İşyeri Yetkilisi', role: 'company_admin',
      company_id: company.id, osgb_id: 7, subscription_write_allowed: true,
    });
    if (path === '/dashboard/summary') return json(route, {});
    if (path === '/workplace-portal/summary') return json(route,
      summaryError ? {detail: 'Özet servisine ulaşılamıyor.'} : {company_id: company.id, company_name: company.name, counts},
      summaryError ? 500 : 200);
    if (path === '/companies') return json(route, [company]);
    if (path === '/health-records') return json(route, healthRows);
    if (path === '/health-records/summary') return json(route, {
      company_id: company.id,
      total: healthRows.length,
      overdue: 0,
      due_soon: 1,
      fit: 0,
      conditional: healthRows.filter((row) => row.fitness_status === 'conditional').length,
      tracking: healthRows.filter((row) => row.fitness_status === 'tracking').length,
      unfit: healthRows.filter((row) => row.fitness_status === 'unfit').length,
      with_audiometry: null,
      with_spirometry: null,
      with_chest_xray: null,
      with_blood_lead: null,
      lead_high: null,
    });
    if (path === '/health-records/meta') return json(route, {
      record_types: [{code: 'periodic_exam', label: 'Periyodik Muayene'}],
      fitness_statuses: [{code: 'conditional', label: 'Kısıtlı / Şartlı'}],
      exposure_options: [],
    });
    if (path === '/employees/import-template.xlsx' && request.method() === 'GET') {
      employeeTemplateRequests += 1;
      return route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        body: 'PK mock personnel template',
      });
    }
    if (path === '/employees/import-excel' && request.method() === 'POST') {
      const url = new URL(request.url());
      employeeImportRequests.push({
        companyId: url.searchParams.get('company_id'),
        branchId: url.searchParams.get('branch_id'),
      });
      return json(route, {created: 1, updated: 0, reactivated: 0, errors: [], error_count: 0, count: 1});
    }
    if (path === '/employees/bulk-purge' && request.method() === 'POST') {
      const payload = request.postDataJSON();
      bulkPurgePayloads.push(payload);
      const selectedIds = new Set(payload.employee_ids || []);
      employeeRows = employeeRows.filter((employee) => !selectedIds.has(employee.id));
      return json(route, {
        message: `${selectedIds.size} personel kalıcı olarak silindi.`,
        deleted: selectedIds.size,
        linked_skipped: 0,
        requested: selectedIds.size,
      });
    }
    if (path === '/employees') return json(route, employeeRows);
    if (path === '/companies/42/site-qr/ephemeral') {
      qrRequests += 1;
      return json(route, {
        qr_payload: `test-qr-${qrRequests}`, company_id: company.id, company_name: company.name,
        ttl_minutes: 5, expires_at: new Date(Date.now() + 300000).toISOString(),
      });
    }
    if (path === '/companies/qr-render') return route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320"><rect width="320" height="320" fill="white"/><rect x="30" y="30" width="260" height="260" fill="black"/></svg>',
    });
    if (path === '/ohs-committee/candidates') return json(route, committeeCandidates);
    if (path === '/ohs-committee/meta') return json(route, {roles: [
      {code: 'uzman', label: 'İş Güvenliği Uzmanı'},
      {code: 'calisan_temsilcisi', label: 'Çalışan Temsilcisi'},
      {code: 'destek', label: 'Destek Elemanı'},
      {code: 'diger', label: 'Diğer'},
    ]});
    if (path === '/ohs-committee/work-queue') return json(route, {items: [], counts: {}});
    if (path.endsWith('/meta')) return json(route, {roles: [], categories: [], ghs_pictograms: [], measurement_types: [], event_types: []});
    if (path === '/ppe/catalog') return json(route, {categories: [], statuses: [], item_types: {}});
    if (path.endsWith('/due-summary')) return json(route, {total: 0, overdue: 0, due_soon: 0});
    return json(route, []);
  });
  return {
    errors,
    qrRequests: () => qrRequests,
    bulkPurgePayloads: () => bulkPurgePayloads,
    employeeTemplateRequests: () => employeeTemplateRequests,
    employeeImportRequests: () => employeeImportRequests,
  };
}

for (const email of ['isyeri.42@kiosk.isgsuite.tr', 'yetkili@example.com']) {
  test(`${email}: workplace modules open through the common sidebar`, async ({page}, testInfo) => {
    const state = await setup(page, {email});
    const isKiosk = email.endsWith('@kiosk.isgsuite.tr');
    await page.goto('/');
    await expect(page.getByRole('heading', {name: company.name})).toBeVisible();
    await expect(page.locator('.workplace-module-card')).toHaveCount(isKiosk ? 9 : 10);
    await expect(page.getByRole('button', {name: 'Uzaktan Eğitim modülünü aç'})).toHaveCount(isKiosk ? 0 : 1);
    await expect(page.locator('.nav-desktop [data-nav="remote_training"]')).toHaveCount(isKiosk ? 0 : 1);
    await expect(page.getByRole('button', {name: 'KKD Takip modülünü aç'})).toContainText('620 kayıt');
    await page.screenshot({path: testInfo.outputPath('workplace-home.png'), fullPage: true});
    for (const forbidden of ['companies', 'users', 'finance', 'contracts']) {
      await expect(page.locator(`.nav-desktop [data-nav="${forbidden}"]`)).toHaveCount(0);
    }
    for (const [id, title] of modules) {
      const link = page.locator(`.nav-desktop [data-nav="${id}"]`);
      await expect(link).toBeVisible();
      await link.click();
      await expect(page.locator('main.content')).toContainText(title);
      await expect(page).toHaveURL(new RegExp(`m=${id}(?:&|$)`));
    }
    expect(state.errors).toEqual([]);
  });
}

test('the existing QR link keeps its sidebar and manual refresh', async ({page}) => {
  const state = await setup(page);
  await page.clock.install();
  await page.goto('/#m=site_qr_kiosk');
  await expect(page.getByRole('img', {name: 'İşyeri QR'})).toBeVisible();
  await expect(page.locator('.nav-desktop [data-nav="sds"]')).toBeVisible();
  const before = state.qrRequests();
  await page.getByRole('button', {name: /Şimdi yenile/}).click();
  await expect.poll(state.qrRequests).toBeGreaterThan(before);
  const afterManual = state.qrRequests();
  await page.clock.fastForward(295000);
  await expect.poll(state.qrRequests).toBeGreaterThan(afterManual);
  await page.locator('.nav-desktop [data-nav="workplace_home"]').click();
  await expect(page.getByRole('heading', {name: company.name})).toBeVisible();
  const afterLeaving = state.qrRequests();
  await page.clock.fastForward(360000);
  expect(state.qrRequests()).toBe(afterLeaving);
  expect(state.errors).toEqual([]);
});

test('workplace manager sees every own employee health record in a masked read-only view', async ({page}) => {
  const clinicalSecrets = [
    'KLINIK_OZET_GIZLI',
    'ODYO_SONUCU_GIZLI',
    'AKILLI_OZET_GIZLI',
    'HEKIM_RAPORU_GIZLI.pdf',
  ];
  const state = await setup(page, {
    email: 'yetkili@example.com',
    employees: [{
      id: 101,
      company_id: company.id,
      full_name: 'Ayşe Örnek',
      job_title: 'Üretim Personeli',
      department: 'Üretim',
      is_active: true,
    }],
    healthRows: [{
      id: 501,
      company_id: company.id,
      employee_id: 101,
      employee_name: 'Ayşe Örnek',
      job_title: 'Üretim Personeli',
      department: 'Üretim',
      record_type: 'periodic_exam',
      examination_date: '2026-09-01',
      next_examination_date: '2027-09-01',
      fitness_status: 'conditional',
      physician_name: 'Dr. Hekim',
      restrictions: 'Gece vardiyasında çalışamaz',
      summary: clinicalSecrets[0],
      tetkik_summary: clinicalSecrets[1],
      smart_summary: clinicalSecrets[2],
      report_file_name: clinicalSecrets[3],
      has_report: true,
      is_overdue: false,
    }],
  });

  await page.goto('/#m=health');
  const content = page.locator('main.content');
  await expect(content.getByRole('heading', {name: 'Sağlık Gözetimi'})).toBeVisible();
  await expect(content.getByText('İşyeri sağlık takip görünümü — salt okunur')).toBeVisible();
  const healthRow = content.locator('tbody tr').filter({hasText: 'Ayşe Örnek'});
  await expect(healthRow).toHaveCount(1);
  await expect(healthRow).toContainText('Gece vardiyasında çalışamaz');
  await expect(healthRow.getByText('Kısıtlı', {exact: true})).toBeVisible();
  await expect(content.getByRole('button', {name: 'Excel İndir'})).toBeVisible();
  await expect(content.getByRole('button', {name: /İşveren Belgesi/})).toBeVisible();

  for (const label of ['Yeni Kayıt', 'Düzenle', 'EK-2 / Klinik Dosya', 'Rapor', 'Sil']) {
    await expect(content.getByRole('button', {name: label, exact: true})).toHaveCount(0);
  }
  for (const secret of clinicalSecrets) {
    await expect(content).not.toContainText(secret);
  }
  expect(state.errors).toEqual([]);
});

test('workplace password account can open the requested register forms', async ({page}) => {
  const state = await setup(page);
  await page.goto('/#m=sds');
  for (const [id, label] of [
    ['sds', /Yeni Ürün/], ['periyodik_kontrol', /Yeni Kayıt/], ['ortam_olcum', /Yeni Ölçüm/],
  ]) {
    await page.locator(`.nav-desktop [data-nav="${id}"]`).click();
    await page.locator('main.content').getByRole('button', {name: label}).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', {name: /Kapat|Vazgeç|İptal/}).first().click();
  }
  expect(state.errors).toEqual([]);
});

test('committee member picker is wide, readable and keeps the selection flow', async ({page}, testInfo) => {
  await setup(page, {
    committeeCandidates: {
      mandatory: [{
        identity_key: 'professional-17', source_type: 'professional', source_id: 17,
        full_name: 'Ayşe Yılmaz', job_title: 'A Sınıfı İş Güvenliği Uzmanı',
        company_name: company.name, mandatory: true, suggested_role_code: 'uzman',
      }],
      other: [{
        identity_key: 'employee-28', source_type: 'employee', source_id: 28,
        full_name: 'Mehmet Demir', job_title: 'Üretim Sorumlusu', department: 'Üretim',
        company_name: company.name, suggested_role_code: 'calisan_temsilcisi',
      }],
      missing_mandatory: [],
    },
  });
  await page.goto('/#m=isg_kurulu');
  await page.getByRole('button', {name: 'Üye Yönet'}).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('Kurul Üyesi Seçimi');
  const bounds = await dialog.boundingBox();
  expect(bounds?.width).toBeGreaterThan(1000);
  await dialog.getByRole('button', {name: /Mehmet Demir kişisini/}).click();
  await expect(dialog.getByText('Seçilen personel')).toBeVisible();
  await expect(dialog.getByRole('button', {name: /Kurula Ekle/})).toBeEnabled();
  await page.screenshot({path: testInfo.outputPath('committee-member-picker.png'), fullPage: true});
});

test('workplace password account can select and delete its own personnel', async ({page}) => {
  const state = await setup(page, {
    employees: [
      {
        id: 101,
        company_id: company.id,
        branch_id: null,
        full_name: 'Ayşe Örnek',
        national_id_masked: null,
        job_title: 'Üretim Personeli',
        department: 'Üretim',
        start_date: '2026-09-01',
        special_status: null,
        is_active: true,
      },
    ],
  });
  page.on('dialog', (dialog) => dialog.accept());

  await page.goto('/#m=employees');
  const employeeCheckbox = page.getByRole('checkbox', {name: 'Ayşe Örnek personelini seç'});
  await expect(employeeCheckbox).toBeVisible();

  await page.getByRole('button', {name: 'Görünenlerin Tümünü Seç'}).click();
  await expect(employeeCheckbox).toBeChecked();

  const purgeButton = page.getByRole('button', {name: 'Seçilenleri Kalıcı Sil (1)'}).last();
  await expect(purgeButton).toBeEnabled();
  await purgeButton.click();

  await expect.poll(() => state.bulkPurgePayloads().length).toBe(1);
  expect(state.bulkPurgePayloads()[0]).toEqual({employee_ids: [101], company_id: company.id});
  await expect(page.getByText('Ayşe Örnek')).toHaveCount(0);
  expect(state.errors).toEqual([]);
});

test('workplace password account can download and upload the personnel Excel template', async ({page}) => {
  const state = await setup(page);
  page.on('dialog', (dialog) => dialog.accept());

  await page.goto('/#m=employees');
  const downloadButton = page.getByRole('button', {name: "Örnek Excel'i İndir"});
  const uploadInput = page.locator('input[type="file"][accept=".xlsx"]');

  await expect(downloadButton).toBeVisible();
  await expect(page.getByText(/Dosya yalnızca kendi işyerinize aktarılır/)).toBeVisible();
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/employees/import-template.xlsx')),
    downloadButton.click(),
  ]);
  expect(state.employeeTemplateRequests()).toBe(1);

  await uploadInput.setInputFiles({
    name: 'doldurulan-personel-sablonu.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('PK mock filled personnel workbook'),
  });

  await expect.poll(() => state.employeeImportRequests().length).toBe(1);
  expect(state.employeeImportRequests()[0]).toEqual({companyId: String(company.id), branchId: null});
  expect(state.errors).toEqual([]);
});

test('a fresh-tab module link is preserved', async ({page}) => {
  await setup(page);
  await page.goto('/#m=capa');
  await expect(page.locator('main.content')).toContainText('DÖF Yönetimi');
  await expect(page).toHaveURL(/m=capa$/);
});

test('summary failure remains visible without blocking the modules', async ({page}) => {
  await setup(page, {summaryError: true});
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Kayıt sayıları yüklenemedi');
  await expect(page.locator('.workplace-module-card')).toHaveCount(9);
  await expect(page.locator('.workplace-module-grid')).not.toContainText('0 kayıt');
  await page.getByRole('button', {name: 'SDS / PKD modülünü aç'}).click();
  await expect(page).toHaveURL(/m=sds$/);
});

test('mobile workplace navigation exposes all nine modules without overflow', async ({page}, testInfo) => {
  await page.setViewportSize({width: 390, height: 844});
  await setup(page);
  await page.goto('/');
  await expect(page.getByRole('heading', {name: company.name})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: testInfo.outputPath('workplace-mobile.png'), fullPage: true});
  await page.getByRole('button', {name: 'Menü', exact: true}).click();
  const menu = page.getByRole('dialog', {name: 'Tüm modüller'});
  await expect(menu).toBeVisible();
  for (const [id, title] of modules) await expect(menu.getByRole('button', {name: id === 'capa' ? /DÖF/ : title}).first()).toBeVisible();
  await menu.getByRole('button', {name: /SDS/}).click();
  await expect(page).toHaveURL(/m=sds$/);
  await page.goto('/#m=site_qr_kiosk');
  await expect(page.getByRole('img', {name: 'İşyeri QR'})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
