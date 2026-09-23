import {afterAll, expect, test, vi} from 'vitest';
import {act} from 'react';

const fixture = vi.hoisted(() => ({
  root: null,
  companies: [
    {id: 174, name: 'Birinci Test Firması', osgb_id: 4, is_active: true},
    {id: 175, name: 'İkinci Test Firması', osgb_id: 4, is_active: true},
    {id: 176, name: 'Üçüncü Test Firması', osgb_id: 4, is_active: true},
  ],
}));

vi.mock('react-dom/client', async (importOriginal) => {
  const original = await importOriginal();
  return {
    ...original,
    createRoot: (...args) => {
      fixture.root = original.createRoot(...args);
      return fixture.root;
    },
  };
});

vi.mock('./api', async (importOriginal) => ({
  ...await importOriginal(),
  wakeApi: vi.fn(async () => {}),
  api: vi.fn(async (path) => {
    if (path === '/auth/me') return {id: 2, full_name: 'Test Yönetici', role: 'company_admin', osgb_id: 4};
    if (path === '/dashboard/summary') return {};
    if (path === '/companies') return fixture.companies;
    if (path === '/osgb') return [{id: 4, name: 'Test OSGB'}];
    const status = path.match(/^\/companies\/(\d+)\/status$/);
    if (status) return {company: fixture.companies.find((row) => row.id === Number(status[1]))};
    return [];
  }),
}));

afterAll(async () => {
  await act(async () => fixture.root?.unmount());
  vi.unstubAllGlobals();
});

test('Customer 360 keeps the report, URL and both company selectors in sync', async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.stubGlobal('fetch', vi.fn(async () => new Response('[]', {headers: {'Content-Type': 'application/json'}})));
  HTMLElement.prototype.scrollIntoView = vi.fn();
  document.body.innerHTML = '<div id="root"></div>';
  sessionStorage.setItem('isg_token', 'test-token');
  sessionStorage.setItem('isg_selected_company_id', '176');
  localStorage.setItem('isg_pwa_shortcut_choice_v2', JSON.stringify({choice: 'dismissed', time: Number.MAX_SAFE_INTEGER}));
  window.history.replaceState({}, '', '/#m=customer_360&company=174');

  await act(async () => { await import('./main.jsx'); });

  const sidebar = () => document.querySelector('.global-nace-context-desktop select');
  const pagePicker = () => document.querySelector('#customer-360-company-select');
  const expectCompany = async (id) => {
    await vi.waitFor(() => {
      expect(document.querySelector('.customer-360-page h2')?.textContent).toContain(
        fixture.companies.find((row) => row.id === id).name,
      );
      expect(sidebar()?.value).toBe(String(id));
      expect(pagePicker()?.value).toBe(String(id));
      expect(new URLSearchParams(window.location.hash.slice(1)).get('company')).toBe(String(id));
      expect(sessionStorage.getItem('isg_selected_company_id')).toBe(String(id));
    });
  };
  const choose = async (element, id) => {
    await act(async () => {
      element.value = String(id);
      element.dispatchEvent(new Event('change', {bubbles: true}));
    });
  };

  // A deep link takes precedence over a different firm left in the session.
  await expectCompany(174);
  await choose(sidebar(), 175);
  await expectCompany(175);
  await choose(pagePicker(), 176);
  await expectCompany(176);

  // The same route update used by browser Back/Forward must update both pickers.
  await act(async () => {
    window.history.replaceState({}, '', '/#m=customer_360&company=174');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  await expectCompany(174);

  const {api} = await import('./api');
  for (const id of [174, 175, 176]) expect(api).toHaveBeenCalledWith(`/companies/${id}/status`);

  // Clearing the selection must also remove the previous company's report.
  await choose(pagePicker(), '');
  expect(document.querySelector('.customer-360-page')).toBeNull();
  expect(window.location.hash).toBe('#m=companies');
  expect(sidebar()?.value).toBe('');
}, 20_000);
