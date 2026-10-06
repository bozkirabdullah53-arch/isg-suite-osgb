import {test, expect} from '@playwright/test';

async function setup(page, role, {workplace = false, authenticated = true} = {}) {
  const errors = [];
  const mutations = [];
  const isGlobal = role === 'global_admin';
  const section = {id: 20, package_id: 10, code: 'GEN-01', title: 'Ortak Ders', status: 'active', order_index: 1};
  const video = {id: 30, package_id: 10, section_id: 20, title: 'Merkezi Video',
    status: 'published', is_current: true, duration_seconds: 10, revision_no: 1, order_index: 1};
  const packageRow = {id: 10, title: 'Merkezi Ortak Eğitim', code: 'common-basic-ohs', is_shared: true,
    status: 'published', video_count: 1, published_video_count: 1, section_count: 1,
    automatic_exam_ready: true, automatic_exam_question_count: 20,
    sections: [{...section, videos: [video]}]};
  let packageDeleted = false;
  page.on('pageerror', (error) => errors.push(error.message));
  const token = `e30.${Buffer.from(JSON.stringify({sub: '9', exp: Math.floor(Date.now() / 1000) + 3600})).toString('base64')}.fixture`;
  await page.addInitScript(({token, authenticated}) => {
    if (authenticated) sessionStorage.setItem('isg_token', token);
    else {
      sessionStorage.removeItem('isg_token');
      localStorage.removeItem('isg_refresh_cookie');
    }
  }, {token, authenticated});
  const json = (route, body, status = 200) => route.fulfill({
    status, contentType: 'application/json', body: JSON.stringify(body),
  });
  await page.route('**/live', (route) => route.fulfill({status: 204, body: ''}));
  await page.route('**/api/v1/**', (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace('/api/v1', '').replace(/\/$/, '');
    if (path === '/live') return route.fulfill({status: 204, body: ''});
    if (request.method() === 'OPTIONS') return json(route, {});
    if (path === '/auth/login') return json(route, {access_token: token, refresh_cookie: false});
    if (path === '/auth/me' && !request.headers().authorization) return json(route, {detail: 'Oturum gerekli.'}, 401);
    if (path === '/auth/me') return json(route, {
      id: 9, role, full_name: 'Yetki Testi', email: 'permissions@example.com',
      osgb_id: isGlobal ? null : 7, company_id: workplace ? 42 : null,
      is_eisa: isGlobal, subscription_write_allowed: true,
    });
    if (path === '/trainings/remote/meta') return json(route, {
      enabled: true, can_manage: role !== 'read_only', can_operate: role !== 'read_only',
      can_edit_content: isGlobal, can_edit_shared_content: isGlobal,
      workplace_scoped: workplace, can_view_employee_panel: role === 'read_only',
      strict_policy: {enabled: true, force_off: false, package_codes: ['common-basic-ohs']},
    });
    if (request.method() !== 'GET' && path.startsWith('/trainings/remote/catalog/')) {
      mutations.push({method: request.method(), path});
      if (request.method() === 'PATCH' && path === '/trainings/remote/catalog/packages/10') {
        Object.assign(packageRow, request.postDataJSON());
        return json(route, packageRow);
      }
      if (request.method() === 'DELETE' && path === '/trainings/remote/catalog/packages/10') {
        packageDeleted = true;
        return json(route, {deleted: true, history_preserved: true, materialized_program_count: 1});
      }
      return json(route, video, 201);
    }
    if (path === '/trainings/remote/catalog/packages') return json(route, packageDeleted ? [] : [packageRow]);
    if (path === '/trainings/remote/catalog/packages/10') return json(route, packageDeleted ? {detail: 'Paket bulunamadı.'} : packageRow, packageDeleted ? 404 : 200);
    if (path === '/companies') return json(route, [{id: 42, name: 'Yetkili Firma', is_active: true}]);
    if (path === '/dashboard/summary') return json(route, {});
    if (path === '/trainings/remote/certificates') return json(route, {items: []});
    return json(route, []);
  });
  return {errors, mutations};
}

test('global administrator opens the dedicated menu and uploads a shared video without forking', async ({page}) => {
  const state = await setup(page, 'global_admin');
  await page.goto('/#m=eisa_remote_training');
  await expect(page.getByRole('region', {name: 'Global yönetici uzaktan eğitim video yönetimi'})
    .getByRole('heading', {name: 'Uzaktan Eğitim Video Yönetimi', exact: true})).toBeVisible();
  await expect(page.getByRole('button', {name: '+ Yeni eğitim paketi', exact: true})).toBeVisible();
  const catalog = page.getByRole('region', {name: 'Merkezi uzaktan eğitim paket kataloğu'});
  const uploadButton = catalog.locator('[data-sa="upload"]');
  await expect(uploadButton).toBeVisible();
  await expect(catalog.getByRole('button', {name: 'Paket Bilgilerini Düzenle', exact: true})).toBeVisible();
  await expect(catalog.getByRole('button', {name: 'Paketi Sil', exact: true})).toBeVisible();
  await expect(page.getByLabel('Atama yapılacak firma')).toHaveCount(0);
  const chooserPromise = page.waitForEvent('filechooser');
  await uploadButton.click();
  const chooser = await chooserPromise;
  await chooser.setFiles({name: 'global-lesson.mp4', mimeType: 'video/mp4',
    buffer: Buffer.concat([Buffer.from([0, 0, 0, 24]), Buffer.from('ftypisom'), Buffer.alloc(16)])});
  await expect.poll(() => state.mutations.some((item) => item.path === '/trainings/remote/catalog/sections/20/videos')).toBe(true);
  page.once('dialog', (dialog) => dialog.accept());
  await catalog.locator('[data-va="delete"]').click();
  await expect.poll(() => state.mutations.some((item) => item.method === 'DELETE'
    && item.path === '/trainings/remote/catalog/videos/30')).toBe(true);
  expect(state.mutations.some((item) => item.path.endsWith('/fork'))).toBe(false);
  expect(state.errors).toEqual([]);
});

test('global administrator can edit and delete a shared package from the same menu', async ({page}) => {
  const state = await setup(page, 'global_admin');
  await page.goto('/#m=eisa_remote_training');
  const catalog = page.getByRole('region', {name: 'Merkezi uzaktan eğitim paket kataloğu'});
  await catalog.getByRole('button', {name: 'Paket Bilgilerini Düzenle', exact: true}).click();
  await page.getByLabel('Paket adı *', {exact: true}).fill('Global Güncel Eğitim');
  await page.getByRole('button', {name: 'Değişiklikleri Kaydet', exact: true}).click();
  await expect(catalog.getByRole('heading', {name: 'Global Güncel Eğitim', exact: true})).toBeVisible();
  page.once('dialog', (dialog) => dialog.accept());
  await catalog.getByRole('button', {name: 'Paketi Sil', exact: true}).click();
  await expect.poll(() => state.mutations.some((item) => item.method === 'DELETE'
    && item.path === '/trainings/remote/catalog/packages/10')).toBe(true);
  await expect(catalog.getByText('Henüz eğitim paketi yok. Yeni eğitim paketi ekleyebilirsiniz.', {exact: true})).toBeVisible();
  expect(state.errors).toEqual([]);
});

test('global content controls open after signing in from an anonymous session', async ({page}) => {
  const state = await setup(page, 'global_admin', {authenticated: false});
  await page.goto('/#m=eisa_remote_training');
  await page.locator('.login-card input[autocomplete="username"]').fill('global@example.com');
  await page.locator('.login-card input[autocomplete="current-password"]').fill('FixturePassword123!');
  await page.getByRole('button', {name: 'Giriş Yap', exact: true}).click();
  const catalog = page.getByRole('region', {name: 'Merkezi uzaktan eğitim paket kataloğu'});
  await expect(catalog.getByRole('button', {name: 'Paket Bilgilerini Düzenle', exact: true})).toBeVisible();
  await expect(catalog.getByRole('button', {name: 'Paketi Sil', exact: true})).toBeVisible();
  await expect(catalog.locator('[data-sa="upload"]')).toBeVisible();
  expect(state.errors).toEqual([]);
});

for (const role of ['company_admin', 'safety_specialist', 'workplace_physician', 'other_health_personnel']) {
  test(`${role} keeps training assignment and reports while all video controls remain closed`, async ({page}) => {
    const state = await setup(page, role);
    const moduleId = role === 'other_health_personnel' ? 'remote_training' : 'training';
    await page.goto(`/#m=${moduleId}`);
    if (moduleId === 'training') {
      await page.getByRole('tab', {name: 'Uzaktan Eğitim / Belgeler', exact: true}).click();
    }
    await expect(page.getByLabel('Atama yapılacak firma')).toBeVisible();
    await expect(page.getByLabel('Merkezi Ortak Eğitim sektör paketini firmaya seç')).toBeVisible();
    await expect(page.getByText('Firma eğitim atama ve çalışan takip yönetimi', {exact: true})).toBeVisible();
    await expect(page.getByRole('button', {name: '+ Yeni eğitim paketi', exact: true})).toHaveCount(0);
    await expect(page.locator('[data-sa="upload"], [data-va="delete"], [data-va="replace"]')).toHaveCount(0);
    await expect(page.locator('input[type="file"][accept*="video"]')).toHaveCount(0);
    expect(state.mutations).toEqual([]);
    expect(state.errors).toEqual([]);
  });
}

test('workplace users keep their own assignment and document panels', async ({page}) => {
  const state = await setup(page, 'company_admin', {workplace: true});
  await page.goto('/#m=remote_training');
  await expect(page.getByRole('heading', {name: 'Uzaktan Eğitim Atama ve Takip', exact: true})).toBeVisible();
  await expect(page.getByText('Çalışanlarınıza uzaktan eğitim atayın', {exact: true})).toBeVisible();
  await expect(page.getByRole('button', {name: '+ Yeni eğitim paketi', exact: true})).toHaveCount(0);
  await expect(page.locator('[data-sa="upload"], input[type="file"][accept*="video"]')).toHaveCount(0);
  expect(state.errors).toEqual([]);
});
