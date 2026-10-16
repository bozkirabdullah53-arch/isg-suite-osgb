import {act} from 'react';
import {expect, test, vi} from 'vitest';
import {calls, choose, clickNav, companies, companyFailureCases, dashboard, deferred, fixture, mainText, mount, routeCompany, sidebar, travel, visit} from './navigation_app_fixture';

const picker = () => document.querySelector('#osgb-dashboard-company-select');
const visits = () => [...document.querySelectorAll('article.metric')].find((article) => article.querySelector('span')?.textContent === 'Bu Ay Saha Ziyareti')?.querySelector('strong')?.textContent;
async function assertCompany(id) {
  await vi.waitFor(() => {
    expect(visits()).toBe(String(id));
    expect(sidebar()?.value).toBe(String(id));
    expect(picker()?.value).toBe(String(id));
    expect(routeCompany()).toBe(String(id));
    expect(sessionStorage.getItem('isg_selected_company_id')).toBe(String(id));
  });
}

async function assertOverview() {
  await vi.waitFor(() => {
    expect(visits()).toBe('0');
    expect(picker()?.value).toBe('');
    expect(sidebar()?.value).toBe('');
    expect(routeCompany()).toBeNull();
    expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
    expect(mainText()).toContain('OSGB GENEL ÖZETİ');
    expect(mainText()).toContain('Entegrasyon hazırlık');
    expect(mainText()).toContain('ÇSGB denetim hazırlığı');
  });
}

test('OSGB dashboard: fresh entry, both pickers, recorded history, clearing and notifications round trip', async () => {
  await mount('/#m=osgb_dashboard');
  await assertOverview();
  expect(window.history.state.navigationIndex).toBe(0);
  await choose(sidebar(), 174);
  await assertCompany(174);
  await choose(picker(), 175);
  await assertCompany(175);
  await travel('back');
  await assertCompany(174);
  await travel('forward');
  await assertCompany(175);
  await clickNav('notifications');
  expect(window.location.hash).toBe('#m=notifications');
  expect(routeCompany()).toBeNull();
  expect(sidebar()?.value).toBe('');
  await travel('back');
  await assertCompany(175);
  await travel('forward');
  expect(window.location.hash).toBe('#m=notifications');
  await clickNav('osgb_dashboard');
  await assertOverview();
  await choose(picker(), 176);
  await assertCompany(176);
  await choose(sidebar(), '');
  await assertOverview();
  expect(picker()?.value).toBe('');
  expect(routeCompany()).toBeNull();
  expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
  await travel('back');
  await assertCompany(176);
  await travel('forward');
  await assertOverview();
  for (const [path] of fixture.api.mock.calls.filter(([path]) => /^\/(operations\/(dashboard|module-kpis)|osgb\/(oversight|csgb-audit-pack\/summary|integration-readiness))\?/.test(path))) {
    const params = new URLSearchParams(path.split('?')[1]);
    expect(params.get('osgb_id')).toBe('4');
    expect([null, '174', '175', '176']).toContain(params.get('company_id'));
  }
});

test.each(['/', '/#m=osgb_dashboard'])('fresh login at %s renders the dashboard without stored company or manual selection', async (route) => {
  await mount(route, {storedCompany: ''});
  await assertOverview();
  expect(mainText()).not.toContain('Başlamak için firma seçiniz');
  expect(document.querySelector('.global-nace-context-mobile-card select')?.value).toBe('');
});

test('initial overview works while the company directory loads without choosing a company', async () => {
  const pending = deferred();
  fixture.overrides.set('/companies', pending.promise);
  await mount('/', {storedCompany: ''});
  await assertOverview();
  expect(calls('/operations/dashboard?').every(([path]) => !path.includes('company_id='))).toBe(true);
  await act(async () => pending.resolve([{...companies[0], is_active: false}, ...companies.slice(1)]));
  await assertOverview();
});

test.each([[], companies.map((company) => ({...company, is_active: false}))])('initial dashboard with no active companies remains finite', async (rows) => {
  fixture.companies = rows;
  await mount('/', {storedCompany: ''});
  await assertOverview();
  expect(picker()?.value).toBe('');
  expect(mainText()).not.toContain('Sistem yükleniyor');
});

test('initial dashboard directory error can retry the overview', async () => {
  fixture.overrides.set('/companies', new Error('Firma dizini hatası'));
  await mount('/', {storedCompany: ''});
  await assertOverview();
  fixture.overrides.delete('/companies');
  await act(async () => [...document.querySelectorAll('button')].find((button) => button.textContent === 'Tekrar dene').click());
  await assertOverview();
});

test('navigation back to the overview while the directory is loading keeps company empty', async () => {
  const pending = deferred();
  fixture.overrides.set('/companies', pending.promise);
  await mount('/', {storedCompany: ''});
  await visit('#m=osgb_dashboard&company=175');
  await visit('#m=osgb_dashboard');
  await act(async () => pending.resolve(companies));
  expect(picker()?.value).toBe('');
  await assertOverview();
});

test('mobile company picker shares dashboard state', async () => {
  await mount('/#m=osgb_dashboard&company=174');
  await choose(document.querySelector('.global-nace-context-mobile-card select'), 175);
  await assertCompany(175);
});

test('a slow overview response cannot replace the selected company', async () => {
  const pending = deferred();
  fixture.overrides.set('/operations/dashboard?osgb_id=4', pending.promise);
  await mount('/');
  await choose(picker(), 175);
  await assertCompany(175);
  await act(async () => pending.resolve({visits_this_month: 999}));
  await assertCompany(175);
});

test('overview never guesses a missing user OSGB from the organization list', async () => {
  fixture.user = {...fixture.user, osgb_id: null};
  await mount('/');
  expect(calls('/operations/dashboard?')).toHaveLength(0);
  expect(mainText()).toContain('OSGB bilgisi eksik');
});

test('unauthorized module returns to the role home without carrying company context', async () => {
  await mount('/#m=eisa_overview&company=174');
  expect(window.location.hash).toBe('#m=osgb_dashboard');
  await assertOverview();
});

test('unauthorized history entry also clears a company when home is already active', async () => {
  await mount('/#m=osgb_dashboard&company=174');
  await visit('#m=eisa_overview&company=175');
  expect(window.location.hash).toBe('#m=osgb_dashboard');
  expect(picker()?.value).toBe('');
  await assertOverview();
  expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
});

companyFailureCases({module: 'osgb_dashboard', picker, endpoint: (id) => `/operations/dashboard?osgb_id=4&company_id=${id}`, result: dashboard, assertCompany});
