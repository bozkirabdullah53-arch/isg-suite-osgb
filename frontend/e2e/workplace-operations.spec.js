import {test, expect} from '@playwright/test';

const company = {id: 42, name: 'ÖRNEK AKÜ VE OTOMOTİV SAN. TİC. LTD. ŞTİ.', is_active: true};
const counts = {employees: 24, ppe: 620, sds: 12, periodic: 18, measurements: 9, nearMiss: 4, accidents: 1, capa: 8};
const modules = [
  ['employees', /Personel/], ['ppe', /KKD/], ['sds', /SDS/],
  ['periyodik_kontrol', /Periyodik/], ['ortam_olcum', /Ortam/],
  ['near_miss', /Ramak/], ['accident', /Kaz/], ['capa', /DÖF Yönetimi/],
  ['isg_kurulu', /İSG Kurulu/],
];

async function setup(page, {email = 'isyeri.42@kiosk.isgsuite.tr', summaryError = false} = {}) {
  const errors = [];
  let qrRequests = 0;
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
    if (path === '/ohs-committee/candidates') return json(route, {mandatory: [], other: [], missing_mandatory: []});
    if (path === '/ohs-committee/work-queue') return json(route, {items: [], counts: {}});
    if (path.endsWith('/meta')) return json(route, {roles: [], categories: [], ghs_pictograms: [], measurement_types: [], event_types: []});
    if (path === '/ppe/catalog') return json(route, {categories: [], statuses: [], item_types: {}});
    if (path.endsWith('/due-summary')) return json(route, {total: 0, overdue: 0, due_soon: 0});
    return json(route, []);
  });
  return {errors, qrRequests: () => qrRequests};
}

for (const email of ['isyeri.42@kiosk.isgsuite.tr', 'yetkili@example.com']) {
  test(`${email}: workplace modules open through the common sidebar`, async ({page}, testInfo) => {
    const state = await setup(page, {email});
    await page.goto('/');
    await expect(page.getByRole('heading', {name: company.name})).toBeVisible();
    await expect(page.locator('.workplace-module-card')).toHaveCount(9);
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
