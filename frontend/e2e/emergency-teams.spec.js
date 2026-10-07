import {test, expect} from '@playwright/test';

const company = {id: 1, name: 'Örnek İşyeri', hazard_class: 'Çok Tehlikeli', sgk_registry_no: '1234567890'};
const employee = {id: 11, company_id: 1, full_name: 'Ayşe Yılmaz', job_title: 'Operatör', phone: '05550000000', is_active: true};
const team = {id: 7, company_id: 1, name: 'Söndürme Ekibi', type_code: 'sondurme', asil_count: 0, yedek_count: 0, min_members: 1};

async function prepare(page, {role = 'safety_specialist', downloadError = false, saveError = false} = {}) {
  const saved = [];
  const posts = [];
  const token = `test.${Buffer.from(JSON.stringify({exp: 4102444800})).toString('base64url')}.test`;
  await page.addInitScript((value) => sessionStorage.setItem('isg_token', value), token);
  await page.route('**/live', (route) => route.fulfill({status: 204, body: ''}));
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '');
    const headers = {'Access-Control-Allow-Origin': request.headers().origin || 'http://127.0.0.1:4173', 'Access-Control-Allow-Credentials': 'true', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS'};
    const json = (body, status = 200) => route.fulfill({status, headers, contentType: 'application/json', body: JSON.stringify(body)});
    if (request.method() === 'OPTIONS') return route.fulfill({status: 204, headers, body: ''});
    if (path === '/live') return route.fulfill({status: 204, headers, body: ''});
    if (path === '/auth/me') return json({id: 3, full_name: 'Örnek Uzman', role, company_id: 1, osgb_id: 4});
    if (path === '/auth/refresh') return json({access_token: 'test-token', token_type: 'bearer'});
    if (path === '/dashboard/summary') return json({});
    if (path === '/companies') return json([company, {id: 2, name: 'İkinci İşyeri'}]);
    if (path === '/employees') return json(url.searchParams.get('company_id') === '1' ? [employee] : []);
    if (path === '/emergency-teams/meta') return json({team_types: [{id: 1, code: 'sondurme', name: team.name}]});
    if (path === '/emergency-teams/overview') return json({company: {...company, id: Number(url.searchParams.get('company_id'))}, teams: [team], kpis: {}, warnings: [], can_edit: role === 'safety_specialist'});
    if (path === '/emergency-teams/assignments' && request.method() === 'POST') {
      const payload = request.postDataJSON(); posts.push(payload);
      if (saveError) return json({detail: 'Bu personel zaten bu ekibin üyesi.'}, 409);
      const row = {...payload, id: 41, employee_name: employee.full_name, team_name: team.name, cert_status: 'grey'};
      saved.push(row); return json(row);
    }
    if (path === '/emergency-teams/assignments') return json(url.searchParams.get('company_id') === '1' ? saved : []);
    if (path === '/emergency-teams/assignments/41/letter.pdf') {
      if (downloadError) return json({detail: 'PDF şu anda alınamıyor.'}, 503);
      return route.fulfill({status: 200, headers, contentType: 'application/pdf', body: '%PDF-1.4\n%%EOF'});
    }
    if (path === '/emergency-teams/export.pdf' || path === '/emergency-teams/export.xlsx') {
      const format = path.endsWith('.pdf') ? 'pdf' : 'xlsx';
      return route.fulfill({status: 200, headers: {...headers, 'Content-Disposition': `attachment; filename="acil-durum-ekipleri-1.${format}"`},
        contentType: format === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        body: format === 'pdf' ? '%PDF-1.4\n%%EOF' : 'PK-test-report'});
    }
    return json([]);
  });
  await page.goto('/#m=acil_ekipler');
  await expect(page.getByRole('heading', {name: 'Acil Durum Ekipleri / Destek Elemanları'})).toBeVisible();
  return {posts, saved};
}

async function fillAssignment(page) {
  await page.getByRole('button', {name: 'Destek Elemanı Ekle', exact: true}).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('combobox', {name: 'Personel', exact: true}).selectOption('11');
  await expect(dialog.getByLabel('Görev / Unvan', {exact: true})).toHaveValue('Operatör');
  await dialog.getByLabel('İşveren / İşveren vekili').fill('İşveren Adı');
  await dialog.getByLabel('Ekip lideri').check();
  return dialog;
}

for (const viewport of [{name: 'desktop', width: 1440, height: 900}, {name: 'mobile', width: 390, height: 844}]) {
  for (const theme of ['classic', 'modern']) {
    test(`${viewport.name} ${theme}: simplify the form, keep the dialog visible, save and download`, async ({page}, testInfo) => {
      await page.setViewportSize(viewport);
      await page.addInitScript((value) => localStorage.setItem('isg_ui_theme', value), theme);
      const {posts} = await prepare(page);
      await page.evaluate((value) => document.documentElement.setAttribute('data-ui-theme', value), theme);
      const dialog = await fillAssignment(page);
      await expect(dialog.getByLabel('Bölüm', {exact: true})).toHaveCount(0);
      await expect(dialog.getByLabel('Sicil No', {exact: true})).toHaveCount(0);
      expect(await dialog.evaluate((node) => node.parentElement.parentElement === document.body)).toBe(true);
      const header = dialog.locator('header');
      await dialog.evaluate((node) => {node.scrollTop = 0;});
      const headerBox = await header.boundingBox();
      expect(headerBox.y).toBeGreaterThanOrEqual(0);
      expect(headerBox.x).toBeGreaterThanOrEqual(0);
      expect(headerBox.x + headerBox.width).toBeLessThanOrEqual(viewport.width);
      const checkBox = await dialog.getByLabel('Ekip lideri').boundingBox();
      expect(checkBox.width).toBeLessThanOrEqual(22);
      for (const name of ['İptal', 'Kaydet', 'Kaydet ve Yazıyı İndir']) {
        const action = dialog.getByRole('button', {name, exact: true});
        expect(await action.evaluate((node) => {
          const box = node.getBoundingClientRect();
          return node.contains(document.elementFromPoint(box.right - 12, box.top + 4));
        })).toBe(true);
      }
      await page.screenshot({path: testInfo.outputPath('assignment-form.png')});
      const download = page.waitForEvent('download');
      await dialog.getByRole('button', {name: 'Kaydet ve Yazıyı İndir'}).click();
      expect((await download).suggestedFilename()).toBe('gorevlendirme-yazisi-41.pdf');
      await expect(dialog).toHaveCount(0);
      await expect(page.getByRole('status')).toContainText('Ayşe Yılmaz için görevlendirme kaydedildi.');
      expect(posts).toHaveLength(1);
      expect(posts[0]).toMatchObject({company_id: 1, employee_id: 11, is_leader: true, role_title: 'Operatör'});
      expect(posts[0]).not.toHaveProperty('section');
      expect(posts[0]).not.toHaveProperty('personnel_no');
      await page.locator('.emergency-teams-page').getByRole('combobox', {name: 'İşyeri', exact: true}).selectOption('2');
      await expect(page.locator('.emergency-team-letter-ready')).toHaveCount(0);
    });
  }
}

test('a failed PDF download keeps the saved assignment and permits retry without another create', async ({page}) => {
  const {posts} = await prepare(page, {downloadError: true});
  const dialog = await fillAssignment(page);
  await dialog.getByRole('button', {name: 'Kaydet ve Yazıyı İndir'}).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator('.banner.danger')).toContainText('PDF şu anda alınamıyor.');
  await expect(page.getByRole('status')).toContainText('görevlendirme kaydedildi.');
  await page.getByRole('status').getByRole('button', {name: 'Görevlendirme Yazısı'}).click();
  expect(posts).toHaveLength(1);
});

test('assignment failures stay visible inside the open dialog', async ({page}) => {
  await prepare(page, {saveError: true});
  const dialog = await fillAssignment(page);
  await dialog.getByRole('button', {name: 'Kaydet', exact: true}).click();
  await expect(dialog.getByRole('alert')).toContainText('Bu personel zaten bu ekibin üyesi.');
  await expect(dialog.getByRole('combobox', {name: 'Personel', exact: true})).toHaveValue('11');
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
});

for (const viewport of [{name: 'desktop', width: 1440, height: 900}, {name: 'mobile', width: 390, height: 844}]) {
  test(`${viewport.name}: workplace account opens its emergency teams and downloads reports`, async ({page}) => {
    await page.setViewportSize(viewport);
    await prepare(page, {role: 'company_admin'});
    const panel = page.locator('.emergency-teams-page');
    const companySelect = panel.getByRole('combobox', {name: 'İşyeri', exact: true});
    await expect(companySelect).toHaveValue('1');
    await expect(companySelect).toBeDisabled();
    await expect(companySelect.locator('option[value="2"]')).toHaveCount(0);
    await expect(panel.getByRole('button', {name: 'Destek Elemanı Ekle', exact: true})).toHaveCount(0);
    await expect(panel.getByRole('button', {name: 'Yeni Ekip', exact: true})).toHaveCount(0);
    await expect(panel.getByRole('button', {name: 'Silinenleri Geri Al', exact: true})).toHaveCount(0);
    await expect(panel.getByRole('button', {name: 'Excel', exact: true})).toBeVisible();
    await expect(panel.getByRole('button', {name: 'PDF', exact: true})).toBeVisible();
    for (const [label, format] of [['Excel', 'xlsx'], ['PDF', 'pdf']]) {
      const downloaded = page.waitForEvent('download');
      await panel.getByRole('button', {name: label, exact: true}).click();
      expect((await downloaded).suggestedFilename()).toBe(`acil-durum-ekipleri-1.${format}`);
    }
    await page.reload();
    await expect(page.getByRole('heading', {name: 'Acil Durum Ekipleri / Destek Elemanları'})).toBeVisible();
  });
}
