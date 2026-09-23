import {act} from 'react';
import {expect, test, vi} from 'vitest';
import {calls, choose, clickNav, companyFailureCases, dashboard, fixture, mainText, mount, routeCompany, sidebar, travel, visit} from './navigation_app_fixture';

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

test('OSGB dashboard: fresh entry, both pickers, recorded history, clearing and notifications round trip', async () => {
  await mount('/#m=osgb_dashboard');
  expect(sidebar()?.value).toBe('');
  expect(picker()?.value).toBe('');
  expect(calls('/operations/dashboard?')).toHaveLength(0);
  expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
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
  expect(picker()?.value).toBe('');
  await choose(picker(), 176);
  await assertCompany(176);
  await choose(sidebar(), '');
  expect(visits()).toBeUndefined();
  expect(picker()?.value).toBe('');
  expect(routeCompany()).toBeNull();
  expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
  await travel('back');
  await assertCompany(176);
  await travel('forward');
  expect(visits()).toBeUndefined();
  for (const [path] of fixture.api.mock.calls.filter(([path]) => /^\/(operations\/(dashboard|module-kpis)|osgb\/(oversight|csgb-audit-pack\/summary|integration-readiness))\?/.test(path))) {
    const params = new URLSearchParams(path.split('?')[1]);
    expect(params.get('osgb_id')).toBe('4');
    expect(['174', '175', '176']).toContain(params.get('company_id'));
  }
});

test('mobile company picker shares dashboard state', async () => {
  await mount('/#m=osgb_dashboard&company=174');
  await choose(document.querySelector('.global-nace-context-mobile-card select'), 175);
  await assertCompany(175);
});

test('unauthorized module returns to the role home without carrying company context', async () => {
  await mount('/#m=eisa_overview&company=174');
  expect(window.location.hash).toBe('#m=osgb_dashboard');
  expect(mainText()).toContain('Başlamak için firma seçiniz');
});

test('unauthorized history entry also clears a company when home is already active', async () => {
  await mount('/#m=osgb_dashboard&company=174');
  await visit('#m=eisa_overview&company=175');
  expect(window.location.hash).toBe('#m=osgb_dashboard');
  expect(picker()?.value).toBe('');
  expect(visits()).toBeUndefined();
  expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
});

companyFailureCases({module: 'osgb_dashboard', picker, endpoint: (id) => `/operations/dashboard?osgb_id=4&company_id=${id}`, result: dashboard, assertCompany});
