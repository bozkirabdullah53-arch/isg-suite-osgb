import {afterAll, expect, test, vi} from 'vitest';
import {act} from 'react';

const fixture = vi.hoisted(() => ({
  root: null,
  pendingCompany: '',
  resolveDashboard: null,
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
    if (path.startsWith('/operations/dashboard?')) {
      const id = new URLSearchParams(path.split('?')[1]).get('company_id');
      const result = {workplaces: 1, visits_this_month: Number(id)};
      if (id === fixture.pendingCompany) {
        return new Promise((resolve) => { fixture.resolveDashboard = () => resolve(result); });
      }
      return result;
    }
    return [];
  }),
}));

afterAll(async () => {
  await act(async () => fixture.root?.unmount());
  vi.unstubAllGlobals();
});

test('OSGB dashboard and sidebar share selection, clearing and company-scoped results', async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.stubGlobal('fetch', vi.fn(async () => new Response('[]', {headers: {'Content-Type': 'application/json'}})));
  HTMLElement.prototype.scrollIntoView = vi.fn();
  document.body.innerHTML = '<div id="root"></div>';
  sessionStorage.setItem('isg_token', 'test-token');
  sessionStorage.setItem('isg_selected_company_id', '176');
  localStorage.setItem('isg_pwa_shortcut_choice_v2', JSON.stringify({choice: 'dismissed', time: Number.MAX_SAFE_INTEGER}));
  window.history.replaceState({}, '', '/#m=osgb_dashboard');

  await act(async () => { await import('./main.jsx'); });

  const sidebar = () => document.querySelector('.global-nace-context-desktop select');
  const pagePicker = () => [...document.querySelectorAll('main .field select')].find(
    (select) => select.closest('label')?.textContent.includes('Firma / işyeri'),
  );
  const visits = () => [...document.querySelectorAll('article.metric')].find(
    (article) => article.querySelector('span')?.textContent === 'Bu Ay Saha Ziyareti',
  )?.querySelector('strong')?.textContent;
  const choose = async (element, id) => {
    await act(async () => {
      element.value = String(id);
      element.dispatchEvent(new Event('change', {bubbles: true}));
    });
  };
  const expectSelection = async (id) => {
    await vi.waitFor(() => {
      expect(sidebar()?.value).toBe(String(id));
      expect(pagePicker()?.value).toBe(String(id));
      expect(sessionStorage.getItem('isg_selected_company_id') || '').toBe(String(id));
    });
  };
  const expectCompany = async (id) => {
    await expectSelection(id);
    await vi.waitFor(() => expect(visits()).toBe(String(id)));
  };
  const {api} = await import('./api');

  // Opening the OSGB page must not silently select a previously viewed firm.
  await vi.waitFor(() => expect(sidebar()?.disabled).toBe(false));
  await expectSelection('');
  expect(api.mock.calls.some(([path]) => path.startsWith('/operations/dashboard?'))).toBe(false);

  // A sidebar selection remounts the page boundary; it must still reach the page.
  await choose(sidebar(), 174);
  await expectCompany(174);
  await choose(pagePicker(), 175);
  await expectCompany(175);

  await choose(sidebar(), '');
  await expectSelection('');
  expect(visits()).toBeUndefined();
  await choose(pagePicker(), 176);
  await expectCompany(176);
  await choose(pagePicker(), '');
  await expectSelection('');
  expect(visits()).toBeUndefined();

  // A late response for the old firm must never replace the current firm's data.
  fixture.pendingCompany = '174';
  await choose(sidebar(), 174);
  await expectSelection(174);
  await vi.waitFor(() => expect(fixture.resolveDashboard).toBeTypeOf('function'));
  await choose(sidebar(), 175);
  await expectCompany(175);
  await act(async () => { fixture.resolveDashboard(); });
  await expectCompany(175);

  // Returning to the page resets both selectors together, without leaking scope.
  for (const module of ['notifications', 'osgb_dashboard']) {
    await act(async () => {
      window.history.replaceState({}, '', `/#m=${module}`);
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
  }
  await expectSelection('');
  expect(visits()).toBeUndefined();

  const scopedCalls = api.mock.calls.map(([path]) => path).filter(
    (path) => /^\/(operations\/(dashboard|module-kpis)|osgb\/(oversight|csgb-audit-pack\/summary|integration-readiness))\?/.test(path),
  );
  for (const path of scopedCalls) {
    const params = new URLSearchParams(path.split('?')[1]);
    expect(params.get('osgb_id')).toBe('4');
    expect(['174', '175', '176']).toContain(params.get('company_id'));
  }
}, 20_000);
