import {test, expect} from '@playwright/test';

const companies = [174, 175, 176].map((id) => ({id, name: `Test Firma ${id}`, osgb_id: 4, is_active: true}));
const selectors = {
  customer_360: '#customer-360-company-select',
  capa: '[aria-label="DÖF firma / işyeri seçiniz"]',
  osgb_dashboard: '#osgb-dashboard-company-select',
};
const sidebar = '.global-nace-context-desktop select';

async function boot(page, route, {theme = 'modern', logged = true} = {}) {
  const calls = [];
  const failures = [];
  page.on('pageerror', (error) => failures.push(error.message));
  const token = `test.${Buffer.from(JSON.stringify({exp: 4102444800})).toString('base64url')}.test`;
  await page.addInitScript(({theme, logged, token}) => {
    localStorage.clear();
    sessionStorage.clear();
    if (logged) sessionStorage.setItem('isg_token', token);
    sessionStorage.setItem('isg_selected_company_id', '176');
    localStorage.setItem('isg_ui_theme', theme);
    localStorage.setItem('isg_pwa_shortcut_choice_v2', JSON.stringify({choice: 'dismissed', time: Number.MAX_SAFE_INTEGER}));
  }, {theme, logged, token});
  await page.route('**/*', async (requestRoute) => {
    const request = requestRoute.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, '');
    const json = (body) => requestRoute.fulfill({json: body});
    if (url.pathname.includes('/api/v1/') || path === '/health') {
      calls.push({path, query: url.search, method: request.method()});
      if (path === '/auth/login' && request.method() === 'POST') return json({access_token: token, refresh_cookie: false});
      if (path === '/auth/logout' && request.method() === 'POST') return json({ok: true});
      if (request.method() !== 'GET') {
        failures.push(`Unexpected write: ${request.method()} ${path}`);
        return requestRoute.fulfill({status: 400, json: {detail: 'Unexpected test write'}});
      }
      if (path === '/health') return json({status: 'ok'});
      if (path === '/auth/me') return json({id: 2, full_name: 'Test Yönetici', role: 'company_admin', osgb_id: 4});
      if (path === '/dashboard/summary') return json({});
      if (path === '/companies') return json(companies);
      if (path === '/osgb') return json([{id: 4, name: 'Test OSGB'}]);
      if (path === '/branches' || path === '/notifications') return json([]);
      if (path === '/osgb-applications/public-info') return json({trial_days: 90});
      if (path === '/trainings/premium-policy') return json({enabled: true, force_off: false, cutover: null, version: 'test', rules: {}});
      if (path === '/osgb-personnel-profiles/readiness') return json({readiness_version: 'osgb-professional-card-v1', osgb_id: 4, enabled: true, visible: true, scope: 'osgb_professionals_only', employee_records_included: false});
      if (path === '/osgb-personnel-profiles/professionals') return json({items: []});
      if (path === '/trainings/sectors') return json(Array.from({length: 500}, (_, id) => ({code: `nace_${id}`, name: `Faaliyet ${id}`})));
      const status = path.match(/^\/companies\/(\d+)\/status$/);
      if (status) return json({company: companies.find((row) => row.id === Number(status[1])), counts: {}, compliance: {}, status_center: {items: [
        {code: 'capa', module: 'capa', title: 'Düzeltici ve önleyici faaliyetler', status_label: 'İzlem'},
      ]}});
      if (/^\/companies\/\d+\/status\/obligations$/.test(path)) return json({items: [], summary: {}, pagination: {page: 1, total: 0, total_pages: 1}, filters: {branches: []}});
      const cid = Number(url.searchParams.get('company_id'));
      if (path === '/incidents/capa-board') return json({company_id: cid, summary: {total: 1, open: 1, overdue: 0, completed: 0}, items: [
        {key: `risk-${cid}`, id: cid, parent_id: cid, company_id: cid, source_type: 'risk', source: 'Risk', code: `DÖF-${cid}`, title: `Test DÖF ${cid}`, is_completed: false},
      ]});
      if (path === '/operations/dashboard') return json({company_id: cid, workplaces: 1, visits_this_month: cid});
      if (['/operations/module-kpis', '/osgb/oversight', '/osgb/csgb-audit-pack/summary', '/osgb/integration-readiness', '/osgb/integrations/status'].includes(path)) return json({});
      failures.push(`Unmocked API: ${path}`);
      return requestRoute.fulfill({status: 404, json: {detail: 'Unmocked endpoint'}});
    }
    if (url.pathname === '/training-sectors.json') return json(Array.from({length: 500}, (_, id) => ({code: `nace_${id}`, name: `Faaliyet ${id}`})));
    if (['localhost', '127.0.0.1'].includes(url.hostname)) return requestRoute.continue();
    return requestRoute.abort();
  });
  await page.goto(route);
  return {calls, failures};
}

async function assertCompany(page, module, id, {mobile = false} = {}) {
  const value = String(id);
  await expect(page.locator(mobile ? '.global-nace-context-mobile-card select' : sidebar)).toHaveValue(value);
  await expect(page.locator(selectors[module])).toHaveValue(value);
  await expect.poll(() => page.evaluate(() => sessionStorage.getItem('isg_selected_company_id'))).toBe(value);
  await expect(page).toHaveURL(new RegExp(`#m=${module}&company=${id}$`));
  if (module === 'customer_360') await expect(page.locator('.customer-360-page h2')).toHaveText(`Test Firma ${id}`);
  if (module === 'capa') await expect(page.getByRole('button', {name: `DÖF-${id} kaydını aç`, exact: true})).toBeVisible();
  if (module === 'osgb_dashboard') await expect(page.locator('article.metric').filter({hasText: 'Bu Ay Saha Ziyareti'}).locator('strong')).toHaveText(value);
}

for (const theme of ['classic', 'modern']) {
  for (const module of Object.keys(selectors)) {
    test(`${module}: native Back/Forward, reload, clearing and isolation (${theme})`, async ({page}) => {
      const {calls, failures} = await boot(page, `/#m=${module}&company=174`, {theme});
      await assertCompany(page, module, 174);
      await page.locator(sidebar).selectOption('175');
      await assertCompany(page, module, 175);
      await page.locator(selectors[module]).selectOption('176');
      await assertCompany(page, module, 176);
      await page.goBack();
      await assertCompany(page, module, 175);
      await page.goBack();
      await assertCompany(page, module, 174);
      await page.goForward();
      await assertCompany(page, module, 175);
      await page.goForward();
      await assertCompany(page, module, 176);
      await page.reload();
      await assertCompany(page, module, 176);
      await page.locator(selectors[module]).selectOption('');
      await expect(page.locator(sidebar)).toHaveValue('');
      await expect.poll(() => page.evaluate(() => sessionStorage.getItem('isg_selected_company_id'))).toBeNull();
      await expect(page).toHaveURL(new RegExp(`#m=${module === 'customer_360' ? 'companies' : module}$`));
      await page.goBack();
      await assertCompany(page, module, 176);
      await page.goForward();
      await expect(page.locator(sidebar)).toHaveValue('');
      expect(calls.every(({method}) => method === 'GET')).toBe(true);
      expect(failures).toEqual([]);
    });
  }
}

test('dashboard selection returns with native Back after notifications; mobile selectors agree', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  const {failures} = await boot(page, '/#m=osgb_dashboard&company=174');
  await assertCompany(page, 'osgb_dashboard', 174, {mobile: true});
  await page.locator('.global-nace-context-mobile-card select').selectOption('175');
  await assertCompany(page, 'osgb_dashboard', 175, {mobile: true});
  await page.setViewportSize({width: 1440, height: 1000});
  await page.locator('button[data-nav="notifications"]').first().click();
  await expect(page).toHaveURL(/#m=notifications$/);
  await page.goBack();
  await assertCompany(page, 'osgb_dashboard', 175);
  await page.goForward();
  await expect(page).toHaveURL(/#m=notifications$/);
  expect(failures).toEqual([]);
});

test('login/logout and both public applications work with only mocked requests', async ({page}) => {
  const {calls, failures} = await boot(page, '/', {logged: false});
  await expect(page.getByRole('button', {name: 'Giriş Yap', exact: true})).toBeVisible();
  await page.locator('.login-application-button--specialist').click();
  await expect(page).toHaveURL(/#apply=specialist$/);
  await expect(page.locator('form')).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('button', {name: 'Giriş Yap', exact: true})).toBeVisible();
  await page.locator('.login-application-button--osgb').click();
  await expect(page).toHaveURL(/#apply=osgb$/);
  await expect(page.locator('form')).toBeVisible();
  await page.goBack();
  // Direct hash edits must still use the public hashchange listener.
  await page.evaluate(() => { window.location.hash = 'apply=specialist'; });
  await expect(page.locator('form')).toBeVisible();
  await page.goBack();
  await page.locator('input[autocomplete="username"]').fill('navigation@example.test');
  await page.locator('input[type="password"]').fill('test-only-password');
  await page.getByRole('button', {name: 'Giriş Yap', exact: true}).click();
  await expect(page).toHaveURL(/#m=osgb_dashboard$/);
  await expect(page.locator('#osgb-dashboard-company-select')).toBeVisible();
  await page.getByRole('button', {name: 'Çıkış', exact: true}).first().click();
  await expect(page.getByRole('button', {name: 'Giriş Yap', exact: true})).toBeVisible();
  expect(calls.filter(({method}) => method !== 'GET').map(({path}) => path)).toEqual(['/auth/login', '/auth/logout']);
  expect(failures).toEqual([]);
});
