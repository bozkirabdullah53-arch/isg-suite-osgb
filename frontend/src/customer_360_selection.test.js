import {act} from 'react';
import {expect, test, vi} from 'vitest';
import {calls, choose, companies, companyFailureCases, fixture, mount, routeCompany, sidebar, status, travel} from './navigation_app_fixture';

const picker = () => document.querySelector('#customer-360-company-select');
async function assertCompany(id) {
  await vi.waitFor(() => {
    expect(document.querySelector('.customer-360-page h2')?.textContent).toContain(companies.find((row) => row.id === id).name);
    expect(sidebar()?.value).toBe(String(id));
    expect(picker()?.value).toBe(String(id));
    expect(routeCompany()).toBe(String(id));
    expect(sessionStorage.getItem('isg_selected_company_id')).toBe(String(id));
  });
}

test.each(['classic', 'modern'])('Customer 360: deep link, both selectors, recorded Back/Forward, clear and reopen (%s)', async (theme) => {
  await mount('/#m=customer_360&company=174', {theme});
  await assertCompany(174);
  const initialIndex = window.history.state.navigationIndex;
  await choose(sidebar(), 175);
  await assertCompany(175);
  expect(window.history.state.navigationIndex).toBe(initialIndex + 1);
  await choose(picker(), 176);
  await assertCompany(176);
  await travel('back');
  await assertCompany(175);
  await travel('back');
  await assertCompany(174);
  await travel('forward');
  await assertCompany(175);
  await travel('forward');
  await assertCompany(176);
  await choose(picker(), '');
  expect(document.querySelector('.customer-360-page')).toBeNull();
  expect(window.location.hash).toBe('#m=companies');
  expect(sidebar()?.value).toBe('');
  expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
  await travel('back');
  await assertCompany(176);
  await travel('forward');
  expect(window.location.hash).toBe('#m=companies');
  await choose(sidebar(), 174);
  await act(async () => [...document.querySelectorAll('button')].find((button) => button.textContent.includes('360')).click());
  await assertCompany(174);
  await act(async () => [...document.querySelectorAll('.customer-360-page button')].find((button) => button.textContent.includes('İşyerleri')).click());
  expect(window.location.hash).toBe('#m=companies');
  expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
  for (const id of [174, 175, 176]) expect(calls(`/companies/${id}/status`).length).toBeGreaterThan(0);
});

test('Customer 360 normalizes legacy query and company ID without carrying query scope to companies', async () => {
  await mount('/?m=customer_360&company_id=00174');
  await assertCompany(174);
  expect(window.location.search).toBe('');
  await choose(picker(), '');
  expect(window.location.href).not.toContain('company');
});

test('Customer 360: empty deep link finishes at a safe screen', async () => {
  await mount('/#m=customer_360');
  expect(document.querySelector('.customer-360-page')).toBeNull();
  expect(calls('/companies/174/status')).toHaveLength(0);
  expect(sidebar()?.value).toBe('');
});

companyFailureCases({module: 'customer_360', picker, endpoint: (id) => `/companies/${id}/status`, result: status, assertCompany});
