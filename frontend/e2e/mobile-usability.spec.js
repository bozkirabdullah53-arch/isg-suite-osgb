import {test, expect} from '@playwright/test';

test.beforeEach(async ({}, testInfo) => {
  if (testInfo.project.name === 'mobile-webkit') test.setTimeout(120_000);
});

const company = {id: 176, name: 'Mobil Görünüm Test İşyerinin Uzun Ticari Unvanı', is_active: true};
const employees = [
  {id: 1, company_id: 176, branch_id: 11, full_name: 'Ayşe Uzun İsimli Örnek Personel', job_title: 'Üretim ve kalite kontrol sorumlusu', department: 'Üretim', is_active: true, start_date: '2025-01-01'},
  {id: 2, company_id: 176, branch_id: 12, full_name: 'Mehmet Örnek', job_title: 'Depo', department: 'Lojistik', is_active: true},
];

async function boot(page, {theme = 'modern', pendingSave = false, route = '/#m=employees', employeeRows = employees, emergencyMembers = []} = {}) {
  const errors = [];
  const employeeQueries = [];
  let writes = 0;
  let releaseSave;
  const saved = new Promise((resolve) => { releaseSave = resolve; });
  page.on('pageerror', (error) => errors.push(error.message));
  const token = `test.${Buffer.from(JSON.stringify({exp: 4102444800})).toString('base64url')}.test`;
  await page.addInitScript(({token, theme}) => {
    sessionStorage.setItem('isg_token', token);
    sessionStorage.setItem('isg_selected_company_id', '176');
    localStorage.setItem('isg_ui_theme', theme);
    localStorage.setItem('isg_pwa_shortcut_choice_v2', JSON.stringify({choice: 'dismissed', time: Number.MAX_SAFE_INTEGER}));
  }, {token, theme});
  await page.route('**/api/v1/**', async (requestRoute) => {
    const request = requestRoute.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '').replace(/\/$/, '');
    const json = (body) => requestRoute.fulfill({json: body});
    if (path === '/live') return requestRoute.fulfill({status: 204, body: ''});
    if (path === '/employees' && request.method() === 'POST') {
      writes += 1;
      if (pendingSave) await saved;
      return json({id: 3});
    }
    if (request.method() !== 'GET') {
      errors.push(`Unexpected write: ${request.method()} ${path}`);
      return requestRoute.fulfill({status: 400, json: {detail: 'Unexpected test write'}});
    }
    if (path === '/auth/me') return json({id: 2, full_name: 'Mobil Test Uzmanı Uzun Soyadı', role: 'safety_specialist', osgb_id: 4});
    if (path === '/dashboard/summary') return json({});
    if (path === '/companies') return json([company]);
    if (path === '/osgb') return json([{id: 4, name: 'Test OSGB'}]);
    if (path === '/osgb-personnel-profiles/readiness') return json({enabled: false, visible: false, scope: 'osgb_professionals_only'});
    if (path === '/osgb-personnel-profiles/professionals') return json([]);
    if (path === '/branches') return json([{id: 11, company_id: 176, name: 'Üretim'}, {id: 12, company_id: 176, name: 'Depo'}]);
    if (path === '/employees') {
      employeeQueries.push(url.search);
      // Intentionally return both branches: older API responses must not widen selection.
      return json(employeeRows);
    }
    if (path === '/trainings/sectors') return json(Array.from({length: 500}, (_, id) => ({code: `nace_${id}`, name: `Faaliyet ${id}`})));
    if (path === '/trainings/premium-policy') return json({enabled: true, force_off: false, cutover: null, version: 'test', rules: {}});
    if (path === '/osgb-applications/public-info') return json({trial_days: 90});
    if (path === '/annual-plans/meta') return json({categories: [], statuses: []});
    if (path === '/annual-plans') return json([]);
    if (path === '/annual-plans/summary') return json({total: 0, completed: 0, waiting: 0, delayed: 0, by_month: {}});
    if (path === '/notifications') return json([]);
    if (path === '/emergency-teams/meta') return json({team_types: [], memberships: ['asil', 'yedek']});
    if (path === '/emergency-teams/overview') return json({company, employee_count: emergencyMembers.length, teams: [{id: 1, name: 'Kurtarma Ekibi', type_code: 'rescue'}], kpi: {team_count: 1, member_count: emergencyMembers.length}});
    if (path === '/emergency-teams/assignments') return json(emergencyMembers);
    errors.push(`Unmocked API request: ${path}`);
    return json({});
  });
  await page.route('**/live', (requestRoute) => requestRoute.fulfill({status: 204, body: ''}));
  await page.goto(route);
  await expect(page.locator('.app-shell')).toBeVisible({timeout: 30_000});
  return {errors, employeeQueries, writes: () => writes, releaseSave};
}

async function assertControlsInsideViewport(page, selector) {
  const outside = await page.locator(selector).evaluateAll((elements) => elements.flatMap((element) => {
    const rect = element.getBoundingClientRect();
    if (!rect.width || !rect.height) return [];
    return rect.left < -1 || rect.right > window.innerWidth + 1 ? [{text: element.textContent, left: rect.left, right: rect.right}] : [];
  }));
  expect(outside).toEqual([]);
}

async function assertUncovered(page, locator) {
  await locator.scrollIntoViewIfNeeded();
  await expect.poll(() => locator.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    return hit === element || element.contains(hit);
  })).toBe(true);
}

for (const width of [320, 360, 390, 430]) {
  test(`${width}px: filters, cards and 44px header controls stay within the phone`, async ({page}, testInfo) => {
    await page.setViewportSize({width, height: 844});
    const state = await boot(page);
    await expect(page.locator('.employee-card')).toHaveCount(2);
    await expect(page.locator('.employees-table')).toBeHidden();
    await expect(page.locator('.employees-tools')).not.toHaveAttribute('open', '');
    await expect(page.locator('#mobile-assistant-slot button')).toBeVisible();
    if (width === 390) await page.screenshot({path: testInfo.outputPath('personnel-mobile.png'), fullPage: true});
    await assertControlsInsideViewport(page, '.employees-filters select, .employees-page button, .employees-page summary, .employee-card, .header-tools > button, .header-tools .contextual-assistant-launcher');
    for (const control of await page.locator('.header-tools > button, .header-tools .contextual-assistant-launcher').all()) {
      const box = await control.boundingBox();
      expect(Math.round(box.width)).toBeGreaterThanOrEqual(44);
      expect(Math.round(box.height)).toBeGreaterThanOrEqual(44);
    }
    for (const select of await page.locator('.employees-filters select').all()) await assertUncovered(page, select);
    await page.getByLabel('Şube filtresi').selectOption('11');
    await expect(page.locator('.employee-card')).toHaveCount(1);
    await page.getByRole('button', {name: 'Görünenlerin Tümünü Seç'}).click();
    await expect(page.getByRole('button', {name: 'Seçilenleri Kalıcı Sil (1)'})).toBeEnabled();
    expect(state.employeeQueries.at(-1)).toContain('branch_id=11');
    await page.getByLabel('Şube filtresi').selectOption('12');
    await expect(page.getByRole('button', {name: 'Seçilenleri Kalıcı Sil (1)'})).toHaveCount(0);
    await expect(page.locator('.employee-card')).toContainText('Mehmet');
    expect(state.errors).toEqual([]);
  });
}

test('mobile modal stays above utility controls and a pending save is submitted once', async ({page}) => {
  const state = await boot(page, {pendingSave: true});
  const create = page.getByRole('button', {name: 'Personel Ekle'});
  await create.focus();
  await create.click();
  const dialog = page.getByRole('dialog', {name: /Yeni Personel/});
  await expect(dialog.getByRole('textbox', {name: 'Ad Soyad', exact: true})).toBeFocused();
  await expect(page.locator('.contextual-assistant-launcher')).toBeHidden();
  await expect(page.locator('.global-contact-help')).toBeHidden();
  await dialog.getByRole('textbox', {name: 'Ad Soyad', exact: true}).fill('Mobil Test Personeli');
  await assertUncovered(page, dialog.getByRole('textbox', {name: 'Ad Soyad', exact: true}));
  await assertControlsInsideViewport(page, '.modal input, .modal select, .modal button');
  const save = dialog.getByRole('button', {name: 'Kaydet', exact: true});
  await save.click();
  await expect(dialog.getByRole('button', {name: 'Kaydediliyor…'})).toBeDisabled();
  await dialog.locator('form').evaluate((form) => form.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true})));
  expect(state.writes()).toBe(1);
  state.releaseSave();
  await expect(dialog).toHaveCount(0);
  await expect(create).toBeFocused();
  expect(state.errors).toEqual([]);
});

test('assistant, menu and dialogs restore focus and the document scroll lock', async ({page}) => {
  const state = await boot(page);
  const assistant = page.getByRole('button', {name: 'İSG Asistanını aç'});
  await assistant.click();
  await expect(page.getByRole('dialog', {name: 'İSG Asistanı'})).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(assistant).toBeFocused();
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).not.toBe('hidden');
  const menu = page.locator('.nav-mobile-primary button').last();
  await menu.click();
  const sheet = page.getByRole('dialog', {name: 'Tüm modüller'});
  await expect(sheet).toBeVisible();
  await expect(sheet.getByRole('link', {name: 'İletişim / Yardım'})).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(sheet).toHaveCount(0);
  await expect(menu).toBeFocused();
  expect(state.errors).toEqual([]);
});

test('classic theme also renders personnel cards with clear destructive actions', async ({page}) => {
  const state = await boot(page, {theme: 'classic'});
  await expect(page.locator('.employee-card')).toHaveCount(2);
  await page.locator('.employee-card').first().locator('.employee-row-more summary').click();
  const danger = page.locator('.employee-card').first().getByRole('button', {name: 'Kalıcı Sil', exact: true});
  await expect(danger).toHaveCSS('background-color', 'rgb(185, 28, 28)');
  await assertControlsInsideViewport(page, '.employee-card button, .employee-card summary');
  expect(state.errors).toEqual([]);
});

test('annual plan month tiles wrap into two columns on a phone', async ({page}) => {
  const state = await boot(page, {route: '/#m=annual_plans'});
  await expect(page.locator('.annual-month-grid > div')).toHaveCount(12);
  const boxes = await page.locator('.annual-month-grid > div').evaluateAll((items) => items.map((el) => ({x: el.getBoundingClientRect().x, y: el.getBoundingClientRect().y})));
  expect(boxes[0].y).toBe(boxes[1].y);
  expect(boxes[2].y).toBeGreaterThan(boxes[0].y);
  await assertControlsInsideViewport(page, '.annual-month-grid > div');
  expect(state.errors).toEqual([]);
});

for (const theme of ['modern', 'classic']) {
  for (const viewport of [{width: 844, height: 390}, {width: 932, height: 430}]) {
    test(`${theme} ${viewport.width}x${viewport.height}: landscape shell keeps the last personnel row accessible`, async ({page}) => {
      await page.setViewportSize(viewport);
      const employeeRows = Array.from({length: 18}, (_, index) => ({...employees[index % 2], id: index + 1, full_name: `Landscape Personel ${index + 1}`}));
      const state = await boot(page, {theme, employeeRows});
      await expect(page.locator('.employees-table tbody tr')).toHaveCount(18);
      await expect(page.locator('.nav-desktop')).toBeHidden();
      await expect(page.locator('.nav-mobile-primary')).toBeVisible();
      await expect(page.locator('#mobile-assistant-slot button')).toBeVisible();
      await expect(page.locator('.employees-cards')).toBeHidden();
      const aside = await page.locator('.app-shell > aside').boundingBox();
      // WebKit reserves space for the document scrollbar in fixed elements.
      expect(aside.width).toBeGreaterThanOrEqual(viewport.width - 20);
      expect(aside.width).toBeLessThanOrEqual(viewport.width);
      expect(aside.height).toBeLessThan(100);
      await assertControlsInsideViewport(page, '.nav-mobile-primary button, .header-tools > button, .header-tools .contextual-assistant-launcher');
      const table = page.locator('.employees-table');
      await expect.poll(() => table.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
      const lastRow = table.locator('tbody tr').last();
      await assertUncovered(page, lastRow.getByRole('button', {name: 'Düzenle', exact: true}));
      await expect(lastRow).toContainText('Landscape Personel 18');
      expect(await table.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
      expect(state.errors).toEqual([]);
    });
  }

  test(`${theme}: rotation preserves the mobile menu and restores desktop utilities`, async ({page}) => {
    await page.setViewportSize({width: 390, height: 844});
    const state = await boot(page, {theme});
    await expect(page.locator('.employee-card')).toHaveCount(2);
    await page.locator('.nav-mobile-primary button').last().click();
    const menu = page.getByRole('dialog', {name: 'Tüm modüller'});
    await expect(menu).toBeVisible();
    await page.setViewportSize({width: 844, height: 390});
    await expect(menu).toBeVisible();
    await assertUncovered(page, menu.getByRole('link', {name: 'İletişim / Yardım'}));
    await page.keyboard.press('Escape');
    await expect(menu).toHaveCount(0);
    await expect(page.locator('#mobile-assistant-slot button')).toBeVisible();
    await page.locator('#mobile-assistant-slot button').click();
    const assistant = page.getByRole('dialog', {name: 'İSG Asistanı'});
    await expect(assistant).toBeVisible();
    await assertUncovered(page, assistant.getByRole('button', {name: 'İSG Asistanını kapat', exact: true}));
    await page.keyboard.press('Escape');
    await expect(assistant).toHaveCount(0);
    await page.setViewportSize({width: 390, height: 844});
    await expect(page.locator('.employees-table')).toBeHidden();
    await assertUncovered(page, page.locator('.employee-card').last().getByRole('button', {name: 'Düzenle', exact: true}));
    await page.locator('.nav-mobile-primary button').last().click();
    await page.setViewportSize({width: 1440, height: 900});
    await expect(menu).toHaveCount(0);
    await expect(page.locator('.nav-desktop')).toBeVisible();
    await expect(page.locator('#mobile-assistant-slot button')).toHaveCount(0);
    await expect(page.getByRole('button', {name: 'İSG Asistanını aç'})).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.body.style.overflow)).not.toBe('hidden');
    expect(state.errors).toEqual([]);
  });

  test(`${theme}: desktop sidebar labels and final navigation remain accessible`, async ({page}, testInfo) => {
    await page.setViewportSize({width: 1440, height: 900});
    const state = await boot(page, {theme});
    await expect(page.locator('.nav-desktop')).toBeVisible();
    await expect(page.locator('.nav-mobile-primary')).toBeHidden();
    const aside = await page.locator('.app-shell > aside').boundingBox();
    expect(Math.round(aside.width)).toBe(248);
    const first = page.locator('.nav-desktop > button').first();
    expect((await first.boundingBox()).height).toBeGreaterThanOrEqual(44);
    const clipped = await page.locator('.nav-desktop > button > span').evaluateAll((labels) => labels.filter((label) => label.scrollHeight > label.clientHeight + 1 || label.scrollWidth > label.clientWidth + 1).map((label) => label.textContent));
    expect(clipped).toEqual([]);
    await page.screenshot({path: testInfo.outputPath(`sidebar-${theme}.png`)});
    const last = page.locator('.nav-desktop > button').last();
    await assertUncovered(page, last);
    await last.click({trial: true});
    expect(state.errors).toEqual([]);
  });

  test(`${theme}: landscape emergency team table exposes its final row and actions`, async ({page}) => {
    await page.setViewportSize({width: 932, height: 430});
    const emergencyMembers = Array.from({length: 18}, (_, index) => ({id: index + 1, employee_name: `Emergency Member ${index + 1}`, team_id: 1, team_name: 'Kurtarma Ekibi', membership: 'asil', cert_status: 'grey'}));
    const state = await boot(page, {theme, route: '/#m=acil_ekipler', emergencyMembers});
    await page.getByRole('combobox', {name: 'İşyeri', exact: true}).selectOption('176');
    const table = page.getByRole('table').filter({has: page.getByRole('columnheader', {name: 'Ad Soyad', exact: true})});
    await expect(table.locator('tbody tr')).toHaveCount(18, {timeout: 30_000});
    await assertUncovered(page, table.locator('tbody tr').last().getByRole('button', {name: 'Eğitim', exact: true}));
    await expect(table.locator('tbody tr').last()).toContainText('Emergency Member 18');
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    expect(state.errors).toEqual([]);
  });
}
