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
    if (path === '/companies' || path === '/companies?active=true') return fixture.companies;
    if (path === '/osgb') return [{id: 4, name: 'Test OSGB'}];
    const status = path.match(/^\/companies\/(\d+)\/status$/);
    if (status) return {
      company: fixture.companies.find((row) => row.id === Number(status[1])),
      status_center: {items: [
        {code: 'capa', module: 'capa', title: 'Düzeltici ve önleyici faaliyetler', status_label: 'Gecikmiş'},
        {code: 'risk', module: 'risk', title: 'Risk kaydı', status_label: 'Kayıtlı'},
      ]},
    };
    const board = path.match(/^\/incidents\/capa-board\?company_id=(\d+)$/);
    if (board) return {company_id: Number(board[1]), items: [{key: 'r-1', code: `DÖF-${board[1]}`, title: 'Test DÖF', is_completed: false}], summary: {total: 1, open: 1, overdue: 0, completed: 0}};
    return [];
  }),
}));

afterAll(async () => {
  await act(async () => fixture.root?.unmount());
  vi.unstubAllGlobals();
});

test('OSGB company DÖF links survive entry, selection, browser history and status-center navigation', async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.stubGlobal('fetch', vi.fn(async () => new Response('[]', {headers: {'Content-Type': 'application/json'}})));
  HTMLElement.prototype.scrollIntoView = vi.fn();
  document.body.innerHTML = '<div id="root"></div>';
  sessionStorage.setItem('isg_token', 'test-token');
  sessionStorage.setItem('isg_selected_company_id', '176');
  localStorage.setItem('isg_pwa_shortcut_choice_v2', JSON.stringify({choice: 'dismissed', time: Number.MAX_SAFE_INTEGER}));
  // Refresh/deep-link entry must not fall back to the OSGB home page.
  window.history.replaceState({}, '', '/#m=capa&company=174');
  await act(async () => { await import('./main.jsx'); });
  const sidebar = () => document.querySelector('.global-nace-context-desktop select');
  const routeCompany = () => new URLSearchParams(window.location.hash.slice(1)).get('company');
  const expectDof = async (id) => vi.waitFor(() => {
    expect(document.querySelector('main').textContent).toContain(`DÖF-${id}`);
    expect(sidebar()?.value).toBe(String(id));
    expect(routeCompany()).toBe(String(id));
    expect(new URLSearchParams(window.location.hash.slice(1)).get('m')).toBe('capa');
  });
  const choose = async (element, id) => act(async () => {
    element.value = String(id);
    element.dispatchEvent(new Event('change', {bubbles: true}));
  });
  const visit = async (hash) => act(async () => {
    window.history.replaceState({}, '', `/${hash}`);
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  await expectDof(174);
  await choose(sidebar(), 175);
  await expectDof(175);
  await visit('#m=capa&company=174');
  await expectDof(174);
  await visit('#m=workplace_status&company=175');
  await vi.waitFor(() => expect(document.querySelector('.customer-360-page h2')?.textContent).toContain('İkinci Test Firması'));
  await choose(sidebar(), 176);
  await vi.waitFor(() => expect(document.querySelector('.customer-360-page h2')?.textContent).toContain('Üçüncü Test Firması'));
  const dofRow = [...document.querySelectorAll('.customer-360-page tr')].find((row) => row.textContent.includes('Düzeltici ve önleyici faaliyetler'));
  expect(dofRow.querySelector('button')).not.toBeNull();
  const riskRow = [...document.querySelectorAll('.customer-360-page tr')].find((row) => row.textContent.includes('Risk kaydı'));
  expect(riskRow.querySelector('button')).toBeNull();
  await act(async () => dofRow.querySelector('button').click());
  await expectDof(176);
  await choose(sidebar(), '');
  expect(document.querySelector('main').textContent).not.toContain('DÖF-176');
  expect(routeCompany()).toBeNull();
  const {api} = await import('./api');
  expect(api.mock.calls.some(([path]) => path === '/incidents')).toBe(false);
}, 20_000);
