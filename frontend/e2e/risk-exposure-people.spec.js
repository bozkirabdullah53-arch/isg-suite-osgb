import {test, expect} from '@playwright/test';

const companies = [{id: 42, name: 'Akü Test İşletmesi', is_active: true}, {id: 43, name: 'İkinci İşletme', is_active: true}];
const risk = {id: 10, risk_code: 'R-10', hazard: 'Asit sıçraması', hazard_type: 'chemical', department: 'Şarj', activity: 'Asit aktarımı', risk_definition: 'Kimyasal sıçrama', matched_worker_count: 1, source: 'personnel_match'};
const risk2 = {...risk, id: 11, risk_code: 'R-11', hazard: 'Solvent solunması', department: 'Depo'};
const overview = (id) => ({
  company: {...companies.find((c) => c.id === id), active_employee_count: 3}, nace: {},
  summary: {risk_record_count: 2, matched_worker_count: 2},
  risk_types: [{key: 'chemical', label: 'Kimyasal', color: '#ea580c', risk_count: 2, matched_worker_count: 2, dominance_score: 20, percentage: 100}],
  observed_risks: [risk], dominant_risks: [], potential_hazards: [],
});
const roster = (id, role) => ({
  company: companies.find((c) => c.id === id), scope: {label: 'Kimyasal', hazard_type: 'chemical'},
  summary: {matched_worker_count: 2, risk_count: 2, unmatched_risk_count: 0},
  risks: [risk, risk2], can_assign_training: role !== 'workplace_physician',
  employees: [
    {id: 1, full_name: id === 42 ? 'Ayşe Test' : 'İkinci Firma Çalışanı', department: 'Şarj', job_title: 'Dolum görevlisi', matches: [{risk_id: 10, reasons: ['Bölüm bilgisi eşleşiyor: Şarj']}]},
    {id: 2, full_name: 'Mehmet Test', department: 'Depo', job_title: 'Depo görevlisi', matches: [{risk_id: 11, reasons: ['Bölüm bilgisi eşleşiyor: Depo']}]},
    {id: 3, full_name: 'Bakım Çalışanı', department: 'Bakım', job_title: 'Bakım teknisyeni', matches: []},
  ],
});

async function setup(page, role = 'safety_specialist', delayed = false) {
  const errors = [], assignments = [], listRequests = [];
  let pending;
  page.on('pageerror', (error) => errors.push(error.message));
  await page.addInitScript(() => {
    const payload = btoa(JSON.stringify({sub: '9', exp: Math.floor(Date.now() / 1000) + 3600}));
    sessionStorage.setItem('isg_token', `e30.${payload}.fixture`);
    localStorage.setItem('isg_pwa_shortcut_choice_v2', JSON.stringify({choice: 'dismissed', time: Date.now()}));
  });
  const json = (route, body) => route.fulfill({contentType: 'application/json', headers: {'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}, body: JSON.stringify(body)});
  await page.route('**/health', (route) => json(route, {status: 'ok'}));
  await page.route('**/api/v1/**', (route) => {
    const request = route.request(), url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '').replace(/\/$/, '');
    if (request.method() === 'OPTIONS') return json(route, {});
    if (path === '/auth/me') return json(route, {id: 9, role, email: 'fixture@example.test', full_name: 'Test Yetkili', company_id: role === 'company_admin' ? 42 : null, osgb_id: 7, subscription_write_allowed: true});
    if (path === '/companies') return json(route, role === 'company_admin' ? [companies[0]] : companies);
    if (path === '/risks/analytics') return json(route, overview(Number(url.searchParams.get('company_id'))));
    if (path === '/risks/analytics/exposures') {
      const id = Number(url.searchParams.get('company_id'));
      listRequests.push(id);
      if (delayed && id === 42) { pending = () => json(route, roster(id, role)); return; }
      return json(route, roster(id, role));
    }
    if (path === '/trainings/remote/programs') return json(route, [{id: 5, company_id: 42, status: 'published', title: 'Asit güvenliği eğitimi'}]);
    if (path === '/trainings/remote/programs/5/assign') {
      assignments.push(request.postDataJSON());
      return json(route, {created_count: 2, skipped_employee_ids: []});
    }
    if (path === '/trainings/remote/config') return json(route, {enabled: true});
    if (path === '/dashboard/summary') return json(route, {});
    return json(route, []);
  });
  await page.goto('/#m=risk_analytics');
  if (role !== 'company_admin') await page.locator('.ra-company-select select').selectOption('42');
  await expect(page.getByRole('button', {name: 'Kimyasal: 2 çalışanı göster'}).first()).toBeVisible();
  return {errors, assignments, listRequests, release: () => pending?.()};
}

test('opens named reasons, filters a risk, builds a reviewed training list and preserves existing assignment flow', async ({page}) => {
  const state = await setup(page);
  expect(state.listRequests).toHaveLength(0);
  await page.getByRole('button', {name: 'Kimyasal: 2 çalışanı göster'}).first().click();
  const dialog = page.getByRole('dialog', {name: 'Kimyasal'});
  await expect(dialog.getByText('Ayşe Test', {exact: true})).toBeVisible();
  await expect(dialog.getByText('Mehmet Test', {exact: true})).toBeVisible();
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('isg:company-selected', {detail: {companyId: '42'}})));
  await expect(dialog.getByText('Ayşe Test', {exact: true})).toBeVisible();
  await dialog.locator('.ra-person-reasons summary').first().click();
  await expect(dialog.getByText('Bölüm bilgisi eşleşiyor: Şarj')).toBeVisible();
  await dialog.getByLabel('Risk / faaliyet').selectOption('10');
  await expect(dialog.getByText('Mehmet Test', {exact: true})).toHaveCount(0);
  await dialog.getByLabel('Ayşe Test eğitim için seç').check();
  await dialog.getByText('Eğitim listesine manuel eklemek', {exact: false}).click();
  await dialog.getByLabel('Bakım Çalışanı eğitim için seç').check();
  await dialog.getByRole('button', {name: 'Eğitime hazırla', exact: true}).click();
  await dialog.getByRole('combobox', {name: 'Eğitim paketi', exact: true}).selectOption('5');
  const assign = dialog.getByRole('button', {name: 'Seçilen 2 kişiye eğitimi ata'});
  await expect(assign).toBeDisabled();
  await dialog.getByText('Seçilen 2 çalışanı ve eğitim içeriğinin').click();
  await assign.click();
  await expect(dialog.getByRole('status')).toContainText('2 çalışan için eğitim atandı');
  expect(state.assignments).toEqual([{employee_ids: [1, 3], branch_id: null, due_date: null}]);
  await expect(assign).toBeDisabled();
  await dialog.getByRole('button', {name: 'Çalışan listesini kapat'}).click();
  await expect(dialog).toHaveCount(0);
  expect(state.errors).toEqual([]);
});

test('company changes discard the old named response and all selections', async ({page}) => {
  const state = await setup(page, 'safety_specialist', true);
  await page.getByRole('button', {name: 'Kimyasal: 2 çalışanı göster'}).first().click();
  await expect.poll(() => state.listRequests.length).toBe(1);
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('isg:company-selected', {detail: {companyId: '43'}})));
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await state.release();
  await page.getByRole('button', {name: 'Kimyasal: 2 çalışanı göster'}).first().click();
  await expect(page.getByRole('dialog').getByText('İkinci Firma Çalışanı', {exact: true})).toBeVisible();
  await expect(page.getByRole('dialog').getByText('Ayşe Test', {exact: true})).toHaveCount(0);
  await expect(page.getByRole('dialog').getByText('0 çalışan seçildi', {exact: false})).toBeVisible();
  expect(state.errors).toEqual([]);
});

test('physician can inspect on mobile without gaining training assignment controls', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  const state = await setup(page, 'workplace_physician');
  await page.getByRole('button', {name: 'Kimyasal: 2 çalışanı göster'}).first().click();
  await page.getByLabel('Ayşe Test eğitim için seç').check();
  await expect(page.getByRole('button', {name: 'Eğitime hazırla', exact: true})).toHaveCount(0);
  const size = await page.getByRole('dialog').boundingBox();
  expect(size.width).toBeLessThanOrEqual(390);
  await page.screenshot({path: 'test-results/risk-people-mobile.png', fullPage: true});
  expect(state.errors).toEqual([]);
});

test('workplace account keeps its company and the desktop dialog is usable', async ({page}) => {
  const state = await setup(page, 'company_admin');
  await expect(page.locator('.ra-company-select')).toHaveCount(0);
  await page.getByRole('button', {name: 'Kimyasal: 2 çalışanı göster'}).first().click();
  await expect(page.getByRole('dialog').getByText('Ayşe Test', {exact: true})).toBeVisible();
  await page.screenshot({path: 'test-results/risk-people-desktop.png', fullPage: true});
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(state.listRequests).toEqual([42]);
  expect(state.errors).toEqual([]);
});
