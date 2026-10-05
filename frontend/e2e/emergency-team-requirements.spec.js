import {test, expect} from '@playwright/test';

const companies = [
  {id: 174, name: 'Test Firma A', hazard_class: 'Çok Tehlikeli', is_active: true},
  {id: 175, name: 'Test Firma B', hazard_class: 'Az Tehlikeli', is_active: true},
];
const teamTypes = [
  ['sondurme', 'Söndürme Ekibi'], ['kurtarma', 'Kurtarma Ekibi'], ['koruma', 'Koruma Ekibi'],
  ['ilk_yardim', 'İlk Yardım Ekibi'], ['tahliye', 'Tahliye Ekibi'], ['haberlesme', 'Haberleşme Ekibi'],
].map(([code, name], index) => ({id: index + 1, code, name, is_system: true}));

function overview(companyId) {
  const first = companyId === 174;
  const teams = teamTypes.map((type) => {
    const optional = ['tahliye', 'haberlesme'].includes(type.code);
    const required = optional ? null : type.code === 'ilk_yardim' ? (first ? 7 : 3) : (first ? 3 : 2);
    return {
      id: companyId * 10 + type.id, company_id: companyId, type_id: type.id, type_code: type.code,
      type_name: type.name, name: type.name, min_members: 2, required_members: required,
      missing_members: required, minimum_source: optional ? 'risk_assessment' : 'legal',
      minimum_basis: type.code === 'ilk_yardim' ? 'İlkyardım Yönetmeliği m.19' : 'İADY m.11/3',
      minimum_note: optional ? 'Sabit bir yasal kişi oranı yoktur; sayı acil durum planıyla belirlenir.' : 'Çalışan sayısına göre otomatik hesaplandı.',
      asil_count: 0, yedek_count: 0, member_count: 0, cert_summary: {}, warnings: [],
      status: optional ? {code: 'planlama', label: 'Plana göre', tone: 'muted'} : {code: 'kritik', label: 'Kritik', tone: 'danger'},
    };
  });
  return {company: companies.find((company) => company.id === companyId), employee_count: first ? 65 : 51, teams, kpis: {team_count: 6, teams_critical: 4}, warnings: []};
}

async function boot(page) {
  const errors = [];
  let delaySecond = false;
  let releaseSecond;
  let secondRequested;
  const secondStarted = new Promise((resolve) => { secondRequested = resolve; });
  const secondGate = new Promise((resolve) => { releaseSecond = resolve; });
  page.on('pageerror', (error) => errors.push(error.message));
  const token = `test.${Buffer.from(JSON.stringify({exp: 4102444800})).toString('base64url')}.test`;
  await page.addInitScript((token) => {
    localStorage.clear(); sessionStorage.clear();
    sessionStorage.setItem('isg_token', token);
    localStorage.setItem('isg_ui_theme', 'modern');
    localStorage.setItem('isg_pwa_shortcut_choice_v2', JSON.stringify({choice: 'dismissed', time: Number.MAX_SAFE_INTEGER}));
  }, token);
  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, '');
    if (!url.pathname.includes('/api/v1/') && path !== '/live') return route.continue();
    const headers = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Authorization, Content-Type, Idempotency-Key', 'Access-Control-Allow-Methods': 'GET, OPTIONS'};
    const json = (body) => route.fulfill({json: body, headers});
    if (request.method() === 'OPTIONS' || path === '/live') return route.fulfill({status: 204, headers, body: ''});
    if (request.method() !== 'GET') {
      errors.push(`Unexpected write: ${path}`);
      return route.fulfill({status: 400, headers, json: {detail: 'Unexpected write'}});
    }
    if (path === '/auth/me') return json({id: 1, full_name: 'Test Uzman', role: 'safety_specialist', company_id: 174, osgb_id: 4});
    if (path === '/companies') return json(companies);
    if (path === '/dashboard/summary') return json({});
    if (path === '/trainings/premium-policy') return json({enabled: true, rules: {}});
    if (path === '/osgb-applications/public-info') return json({trial_days: 90});
    if (path === '/emergency-teams/meta') return json({team_types: teamTypes, memberships: ['asil', 'yedek']});
    if (path === '/emergency-teams/overview') {
      const companyId = Number(url.searchParams.get('company_id'));
      if (companyId === 175 && delaySecond) { secondRequested(); await secondGate; }
      return json(overview(companyId));
    }
    return json([]);
  });
  await page.goto('/#m=acil_ekipler');
  const summary = page.getByRole('region', {name: 'Otomatik asgari kişi hesabı'});
  await expect(summary).toContainText('65 aktif çalışan');
  return {summary, errors, delay: () => { delaySecond = true; }, secondStarted, releaseSecond};
}

test('computed counts update by company and delayed responses cannot restore old data', async ({page}, testInfo) => {
  const {summary, errors, delay, secondStarted, releaseSecond} = await boot(page);
  const firstAid = page.locator('[aria-label="İlk Yardım Ekibi asgari kişi hesabı"]');
  await expect(firstAid).toContainText('Asgari: 7 kişi');
  await page.screenshot({path: testInfo.outputPath('emergency-teams-desktop.png'), fullPage: true});
  await expect(firstAid).toContainText('Eksik asıl: 7 kişi');
  await expect(page.locator('[aria-label="Tahliye Ekibi asgari kişi hesabı"]')).toContainText('Planla belirlenir');
  const select = page.locator('.emergency-teams-page select').first();
  await select.selectOption('175');
  await expect(summary).toContainText('51 aktif çalışan');
  await expect(firstAid).toContainText('Asgari: 3 kişi');
  await select.selectOption('174');
  await expect(summary).toContainText('65 aktif çalışan');
  delay();
  await select.selectOption('175');
  await secondStarted;
  await expect(summary).toHaveCount(0);
  await expect(firstAid).toHaveCount(0);
  await select.selectOption('174');
  await expect(summary).toContainText('65 aktif çalışan');
  const staleResponse = page.waitForResponse((response) => response.url().includes('/emergency-teams/overview?company_id=175'));
  releaseSecond();
  await staleResponse;
  await expect(summary).toContainText('65 aktif çalışan');
  await expect(firstAid).toContainText('Asgari: 7 kişi');
  await select.selectOption('');
  await expect(summary).toHaveCount(0);
  await expect(firstAid).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('minimum counts and legal basis fit on mobile', async ({page}, testInfo) => {
  await page.setViewportSize({width: 390, height: 844});
  const {summary, errors} = await boot(page);
  const firstAid = page.locator('[aria-label="İlk Yardım Ekibi asgari kişi hesabı"]');
  await expect(firstAid).toContainText('Asgari: 7 kişi');
  await expect(firstAid).toContainText('İlkyardım Yönetmeliği m.19');
  await summary.scrollIntoViewIfNeeded();
  for (const item of [summary, firstAid]) {
    const bounds = await item.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(390);
  }
  expect(errors).toEqual([]);
  await page.screenshot({path: testInfo.outputPath('emergency-teams-mobile.png'), fullPage: true});
});
