import {test, expect} from '@playwright/test';

const members = Array.from({length: 10}, (_, index) => ({
  user_id: index + 1,
  osgb_id: 200 + index,
  specialist_name: index === 0 ? 'Örnek Uzun İsimli İş Güvenliği Uzmanı' : `Örnek Üye ${index + 1}`,
  specialist_email: index === 0 ? 'mobil.uzun.isimli.uye.iletisim.adresi@example.test' : `uye${index + 1}@example.test`,
  effective_status: index % 2 ? 'active' : 'trial',
  package_name: 'Profesyonel Yıllık Abonelik Paketi',
  trial_ends_at: '2027-01-15T12:00:00Z',
  current_period_ends_at: '2027-10-06T12:00:00Z',
  account_active: true,
  certificate_class: 'A',
  certificate_number: 'TEST-12345',
}));
const osgb = {
  id: 31, osgb_id: 31,
  name: 'Örnek Uzun Ticari Unvanlı İş Sağlığı ve Güvenliği OSGB',
  osgb_name: 'Örnek Uzun Ticari Unvanlı İş Sağlığı ve Güvenliği OSGB',
  contact_email: 'uzun.iletisim.adresi.osgb@example.test',
  is_active: true, has_admin_user: true, effective_status: 'past_due',
  package_name: 'Profesyonel OSGB Paketi', current_period_ends_at: '2026-01-01T12:00:00Z',
};

async function bootMembers(page, {theme = 'modern', module = 'eisa_individual_subscriptions', loadError = false} = {}) {
  const errors = [];
  const searches = [];
  const exports = [];
  const writes = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const token = `test.${Buffer.from(JSON.stringify({exp: 4102444800})).toString('base64url')}.test`;
  await page.addInitScript(({token, theme}) => {
    sessionStorage.setItem('isg_token', token);
    localStorage.setItem('isg_ui_theme', theme);
    localStorage.setItem('isg_pwa_shortcut_choice_v2', JSON.stringify({choice: 'dismissed', time: Number.MAX_SAFE_INTEGER}));
  }, {token, theme});
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '').replace(/\/$/, '');
    const json = (body) => route.fulfill({json: body});
    if (path === '/live') return route.fulfill({status: 204, body: ''});
    if (request.method() !== 'GET') {
      writes.push(`${request.method()} ${path}`);
      return route.fulfill({status: 400, json: {detail: 'Test does not allow writes'}});
    }
    if (path === '/auth/me') return json({id: 1, full_name: 'Örnek Global Yönetici', role: 'global_admin'});
    if (path === '/dashboard/summary') return json({});
    if (path === '/eisa/individual-subscriptions/export.pdf') {
      exports.push(url.searchParams.get('q'));
      return route.fulfill({contentType: 'application/pdf', body: '%PDF-1.4\n%%EOF'});
    }
    if (path === '/eisa/individual-subscriptions') {
      if (loadError) return route.fulfill({status: 403, json: {detail: 'Üye listesi okunamadı.'}});
      const q = url.searchParams.get('q') || '';
      searches.push(q);
      return json(members.filter((row) => `${row.specialist_name} ${row.specialist_email}`.toLocaleLowerCase('tr-TR').includes(q.toLocaleLowerCase('tr-TR'))));
    }
    if (path === '/eisa/osgb-users') return json([osgb]);
    if (path === '/eisa/subscriptions') return json([osgb]);
    if (['/companies', '/osgb', '/trainings/sectors', '/notifications', '/eisa/packages'].includes(path)) return json([]);
    if (path === '/trainings/premium-policy') return json({enabled: true, force_off: false, cutover: null, version: 'test', rules: {}});
    if (path === '/osgb-applications/public-info') return json({trial_days: 90});
    errors.push(`Unmocked API request: ${path}`);
    return json({});
  });
  await page.route('**/live', (route) => route.fulfill({status: 204, body: ''}));
  await page.goto(`/#m=${module}`);
  return {errors, searches, exports, writes};
}

async function assertFits(page, selector) {
  const outside = await page.locator(selector).evaluateAll((elements) => elements.flatMap((element) => {
    const rect = element.getBoundingClientRect();
    if (!rect.width || !rect.height) return [];
    return rect.left < -1 || rect.right > window.innerWidth + 1 ? [element.textContent] : [];
  }));
  expect(outside).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

async function assertUncovered(locator) {
  await locator.scrollIntoViewIfNeeded();
  await expect.poll(() => locator.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    return hit === element || element.contains(hit);
  })).toBe(true);
}

for (const theme of ['modern', 'classic']) {
  for (const width of [320, 360, 390, 430]) {
    test(`${theme} ${width}px: member cards, details and pagination are readable and operable`, async ({page}, testInfo) => {
      await page.setViewportSize({width, height: 844});
      const state = await bootMembers(page, {theme});
      const cards = page.locator('.eisa-sub-card');
      await expect(cards).toHaveCount(8);
      await expect(page.locator('.eisa-sub-table')).toBeHidden();
      await expect(cards.first()).toContainText(members[0].specialist_email);
      await expect(cards.first()).toContainText('15.01.2027');
      await assertFits(page, '.eisa-page input, .eisa-page button, .eisa-sub-card, .eisa-sub-card-head > *, .eisa-sub-card-fields dd, .eisa-pagination');
      expect(await page.locator('.nav-mobile-primary button span').evaluateAll((labels) => labels.every((label) => label.scrollWidth <= label.clientWidth))).toBe(true);
      for (const button of await page.locator('.eisa-toolbar button, .eisa-sub-card button, .eisa-pagination button').all()) {
        const box = await button.boundingBox();
        expect(box.height).toBeGreaterThanOrEqual(44);
      }
      expect(await cards.first().locator('.eisa-inline-delete').evaluate((element) => getComputedStyle(element).whiteSpace)).toBe('nowrap');
      if (width === 390) await page.screenshot({path: testInfo.outputPath(`members-${theme}-mobile.png`)});
      const open = cards.first().getByRole('button', {name: `${members[0].specialist_name} bilgilerini aç`});
      await open.click();
      const dialog = page.getByRole('dialog', {name: 'Bireysel üye'});
      await expect(dialog).toBeVisible();
      await expect(dialog).toContainText(members[0].specialist_email);
      await assertFits(page, '.eisa-sub-detail dd, .eisa-sub-detail-modal button');
      await page.keyboard.press('Escape');
      await expect(dialog).toHaveCount(0);
      await expect(open).toBeFocused();
      const next = page.getByRole('button', {name: 'Sonraki', exact: true});
      await assertUncovered(next);
      await next.click();
      await expect(cards).toHaveCount(2);
      await expect(cards.first()).toContainText('Örnek Üye 9');
      await expect(next).toBeDisabled();
      await expect(page.getByRole('navigation', {name: 'Bireysel üyeler sayfalama'})).toContainText('Sayfa 2 / 2');
      await assertUncovered(cards.last().getByRole('button', {name: /bilgilerini aç/}));
      expect(state.errors).toEqual([]);
      expect(state.writes).toEqual([]);
    });
  }
}

test('mobile Enter searches and PDF exports the selected filter without submitting twice', async ({page}) => {
  await page.setViewportSize({width: 360, height: 844});
  const state = await bootMembers(page);
  await expect(page.locator('.eisa-sub-card')).toHaveCount(8);
  const search = page.getByRole('searchbox', {name: 'Arama', exact: true});
  await search.fill('Örnek Üye 9');
  await search.press('Enter');
  await expect(page.locator('.eisa-sub-card')).toHaveCount(1);
  await expect(page.locator('.eisa-sub-card')).toContainText('Örnek Üye 9');
  const download = page.waitForEvent('download');
  await page.getByRole('button', {name: 'PDF İndir', exact: true}).click();
  expect((await download).suggestedFilename()).toMatch(/^bireysel-uyeler-.*\.pdf$/);
  expect(state.exports).toEqual(['Örnek Üye 9']);
  expect(state.searches).toEqual(['', 'Örnek Üye 9']);
  expect(state.writes).toEqual([]);
});

test('cancelled mobile deletion opens no details and sends no write', async ({page}) => {
  await page.setViewportSize({width: 320, height: 844});
  const state = await bootMembers(page);
  await expect(page.locator('.eisa-sub-card')).toHaveCount(8);
  let confirmation = '';
  page.once('dialog', async (dialog) => { confirmation = dialog.message(); await dialog.dismiss(); });
  await page.locator('.eisa-sub-card').first().getByRole('button', {name: /hesabını kaldır/}).click();
  expect(confirmation).toContain(members[0].specialist_name);
  await expect(page.getByRole('dialog', {name: 'Bireysel üye'})).toHaveCount(0);
  await expect(page.locator('.eisa-sub-card')).toHaveCount(8);
  expect(state.writes).toEqual([]);
});

test('mobile shortcuts, full menu and back navigation open the correct member screen', async ({page}) => {
  await page.setViewportSize({width: 320, height: 844});
  const state = await bootMembers(page);
  await expect(page.locator('.eisa-sub-card')).toHaveCount(8);
  await page.locator('.nav-mobile-primary button[data-nav="eisa_osgb_users"]').click();
  await expect(page.getByRole('heading', {name: 'OSGB Kullanıcıları', exact: true})).toBeVisible();
  await expect(page.locator('.eisa-sub-card')).toHaveCount(1);
  await page.getByRole('button', {name: 'Önceki sayfaya dön', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Bireysel Abonelik', exact: true})).toBeVisible();
  await page.locator('.nav-mobile-primary').getByRole('button', {name: 'Menü', exact: true}).click();
  const menu = page.getByRole('dialog', {name: 'Tüm modüller'});
  await menu.getByRole('button', {name: 'Abonelik Yönetimi', exact: true}).click();
  await expect(menu).toHaveCount(0);
  await expect(page.getByRole('heading', {name: 'Abonelik Yönetimi', exact: true})).toBeVisible();
  expect(state.writes).toEqual([]);
  expect(state.errors).toEqual([]);
});

for (const module of ['eisa_osgb_users', 'eisa_subscriptions', 'eisa_subscriptions_expiring', 'eisa_subscriptions_expired']) {
  test(`${module}: OSGB members use the same mobile cards and working detail controls`, async ({page}) => {
    await page.setViewportSize({width: 320, height: 844});
    const state = await bootMembers(page, {module});
    await expect(page.locator('.eisa-sub-card')).toHaveCount(1);
    await assertFits(page, '.eisa-page button, .eisa-page input, .eisa-sub-card, .eisa-sub-card-head > *');
    await page.locator('.eisa-sub-card').getByRole('button', {name: /bilgilerini aç/}).click();
    const dialog = page.getByRole('dialog', {name: module === 'eisa_osgb_users' ? 'OSGB üyesi' : 'OSGB abonesi'});
    await expect(dialog).toContainText(osgb.contact_email);
    await expect(dialog.getByRole('button', {name: module === 'eisa_osgb_users' ? 'Aktife Al' : 'Düzenle', exact: true})).toBeEnabled();
    await assertFits(page, '.eisa-sub-detail dd, .eisa-sub-detail-modal button');
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    expect(state.errors).toEqual([]);
    expect(state.writes).toEqual([]);
  });
}

test('desktop table remains usable with keyboard details and isolated delete actions', async ({page}) => {
  await page.setViewportSize({width: 1440, height: 1000});
  const state = await bootMembers(page);
  const table = page.locator('.eisa-sub-table');
  await expect(table).toBeVisible();
  await expect(page.locator('.eisa-sub-cards')).toBeHidden();
  const open = table.getByRole('button', {name: `${members[0].specialist_name} bilgilerini aç`});
  await open.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog', {name: 'Bireysel üye'})).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(open).toBeFocused();
  page.once('dialog', (dialog) => dialog.dismiss());
  await table.getByRole('button', {name: /hesabını kaldır/}).first().focus();
  await page.keyboard.press('Space');
  await expect(page.getByRole('dialog', {name: 'Bireysel üye'})).toHaveCount(0);
  await assertFits(page, '.eisa-sub-table button');
  expect(state.writes).toEqual([]);
});

test('a failed list request keeps search, refresh and disabled export usable on mobile', async ({page}) => {
  await page.setViewportSize({width: 320, height: 844});
  await bootMembers(page, {loadError: true});
  await expect(page.getByText('Üye listesi okunamadı.', {exact: true})).toBeVisible();
  await expect(page.locator('.eisa-sub-empty')).toContainText('Bireysel üye yok.');
  await expect(page.getByRole('button', {name: 'PDF İndir', exact: true})).toBeDisabled();
  await expect(page.getByRole('button', {name: 'Ara', exact: true})).toBeEnabled();
  await expect(page.getByRole('button', {name: 'Yenile', exact: true})).toBeEnabled();
  await assertFits(page, '.eisa-page button, .eisa-page input');
});
