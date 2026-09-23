import {act} from 'react';
import {afterEach, beforeAll, beforeEach, expect, test, vi} from 'vitest';

const fixture = vi.hoisted(() => ({entry: null, createRoot: null, root: null}));
export {fixture};

vi.mock('react-dom/client', async (importOriginal) => {
  const original = await importOriginal();
  fixture.createRoot = original.createRoot;
  // Capture the real entry once, then mount a fresh App for every scenario.
  return {...original, createRoot: () => ({render: (entry) => { fixture.entry = entry; }})};
});
vi.mock('./api', async (importOriginal) => ({
  ...await importOriginal(),
  wakeApi: vi.fn(async () => {}),
  api: vi.fn(async (path, options = {}) => fixture.respond(path, options)),
}));

export const companies = [
  {id: 174, name: 'Birinci Test Firması', osgb_id: 4, is_active: true},
  {id: 175, name: 'İkinci Test Firması', osgb_id: 4, is_active: true},
  {id: 176, name: 'Üçüncü Test Firması', osgb_id: 4, is_active: true},
];
export const board = (id) => ({
  company_id: id, summary: {total: 1, open: 1, overdue: 0, completed: 0},
  items: [{key: `risk-${id}`, id, parent_id: id, company_id: id, source_type: 'risk',
    source: 'Risk', code: `DÖF-${id}`, title: `Test DÖF ${id}`, is_completed: false}],
});
export const status = (id) => ({
  company: companies.find((row) => row.id === id), counts: {}, compliance: {},
  status_center: {overall_status: 'warning', overall_label: 'İzlem', items: [
    {code: 'capa', module: 'capa', title: 'Düzeltici ve önleyici faaliyetler', status_label: 'İzlem'},
    {code: 'risk', module: 'risk', title: 'Risk kaydı', status_label: 'Kayıtlı'},
  ]},
});
export const dashboard = (id) => ({company_id: id, workplaces: 1, visits_this_month: id});

function defaultResponse(path, options) {
  if (fixture.overrides.has(path)) {
    const value = fixture.overrides.get(path);
    if (value instanceof Error) throw value;
    return typeof value === 'function' ? value(options) : value;
  }
  if (options.method && options.method !== 'GET') {
    fixture.unexpected.push(`${options.method} ${path}`);
    throw new Error(`Unexpected write: ${path}`);
  }
  if (path === '/auth/me') return fixture.user;
  if (path === '/dashboard/summary') return {};
  if (path === '/companies' || path === '/companies?active=true') return fixture.companies;
  if (path === '/osgb') return [{id: 4, name: 'Test OSGB'}];
  if (path === '/branches') return [];
  if (path.startsWith('/notifications?company_id=')) return [];
  const match = path.match(/^\/companies\/(\d+)\/status$/);
  if (match) return status(Number(match[1]));
  if (/^\/companies\/\d+\/status\/obligations\?/.test(path)) {
    return {items: [], summary: {}, filters: {branches: []}, pagination: {page: 1, page_size: 25, total: 0, total_pages: 1}};
  }
  if (path.startsWith('/incidents/capa-board?')) return board(Number(new URLSearchParams(path.split('?')[1]).get('company_id')));
  if (path.startsWith('/operations/dashboard?')) return dashboard(Number(new URLSearchParams(path.split('?')[1]).get('company_id')));
  if (/^\/(operations\/module-kpis|osgb\/(oversight|csgb-audit-pack\/summary|integration-readiness|integrations\/status))\?/.test(path)) return {};
  fixture.unexpected.push(path);
  throw new Error(`Unmocked API endpoint: ${path}`);
}

function installGlobals() {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    if (String(url).includes('training-sectors.json') || String(url).includes('/trainings/sectors')) {
      return new Response(JSON.stringify(Array.from({length: 500}, (_, i) => ({code: `nace_${i}`, name: `Faaliyet ${i}`}))), {headers: {'Content-Type': 'application/json'}});
    }
    if (String(url).endsWith('/osgb-applications/public-info')) return new Response('{}', {headers: {'Content-Type': 'application/json'}});
    fixture.unexpected.push(`fetch ${url}`);
    throw new Error(`Unmocked fetch: ${url}`);
  }));
}

beforeAll(async () => {
  fixture.unexpected = [];
  installGlobals();
  document.body.innerHTML = '<div id="root"></div>';
  await import('./main.jsx');
});
beforeEach(async () => {
  vi.clearAllMocks();
  installGlobals();
  sessionStorage.clear();
  localStorage.clear();
  window.history.replaceState({}, '', '/');
  document.body.innerHTML = '<div id="root"></div>';
  fixture.companies = companies;
  fixture.user = {id: 2, full_name: 'Test Yönetici', role: 'company_admin', osgb_id: 4};
  fixture.overrides = new Map();
  fixture.unexpected = [];
  fixture.respond = defaultResponse;
  fixture.api = (await import('./api')).api;
  vi.spyOn(HTMLElement.prototype, 'scrollIntoView').mockImplementation(() => {});
  fixture.windowAdd = vi.spyOn(window, 'addEventListener');
  fixture.windowRemove = vi.spyOn(window, 'removeEventListener');
  fixture.documentAdd = vi.spyOn(document, 'addEventListener');
  fixture.documentRemove = vi.spyOn(document, 'removeEventListener');
  // happy-dom 17 changes the URL on back()/forward(), but neither emits
  // popstate nor restores history.state. Replay the entries App really wrote.
  // Native browser traversal is covered separately by the Playwright suite.
  fixture.entries = [{state: {}, url: '/'}];
  fixture.cursor = 0;
  fixture.replaceState = window.history.replaceState.bind(window.history);
  const pushState = window.history.pushState.bind(window.history);
  vi.spyOn(window.history, 'pushState').mockImplementation((state, title, url) => {
    fixture.entries.splice(++fixture.cursor);
    fixture.entries.push({state: structuredClone(state), url});
    pushState(state, title, url);
  });
  vi.spyOn(window.history, 'replaceState').mockImplementation((state, title, url) => {
    fixture.entries[fixture.cursor] = {state: structuredClone(state), url};
    fixture.replaceState(state, title, url);
  });
});
afterEach(async () => {
  try {
    await act(async () => fixture.root?.unmount());
    for (const [added, removed, types] of [
      [fixture.windowAdd, fixture.windowRemove, ['popstate', 'hashchange', 'isg:company-selected', 'isg:nace-context-reset']],
      [fixture.documentAdd, fixture.documentRemove, ['change', 'input']],
    ]) {
      for (const [type, handler, options] of added.mock.calls.filter(([type]) => types.includes(type))) {
        expect(removed.mock.calls.some((call) => call[0] === type && call[1] === handler && call[2] === options)).toBe(true);
      }
    }
    expect(fixture.unexpected).toEqual([]);
  } finally {
    fixture.root = null;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.clearAllTimers();
    vi.useRealTimers();
    sessionStorage.clear();
    localStorage.clear();
    window.history.replaceState({}, '', '/');
    document.body.innerHTML = '';
  }
});

export async function mount(route, {logged = true, theme = 'modern'} = {}) {
  if (logged) sessionStorage.setItem('isg_token', 'test-token');
  sessionStorage.setItem('isg_selected_company_id', '176');
  localStorage.setItem('isg_ui_theme', theme);
  localStorage.setItem('isg_pwa_shortcut_choice_v2', JSON.stringify({choice: 'dismissed', time: Number.MAX_SAFE_INTEGER}));
  window.history.replaceState({}, '', route);
  fixture.root = fixture.createRoot(document.getElementById('root'));
  await act(async () => fixture.root.render(fixture.entry));
}
export const sidebar = () => document.querySelector('.global-nace-context-desktop select');
export const routeCompany = () => new URLSearchParams(window.location.hash.slice(1)).get('company');
export const mainText = () => document.querySelector('main')?.textContent || '';
export const calls = (prefix) => fixture.api.mock.calls.filter(([path]) => path.startsWith(prefix));
export async function choose(element, id) {
  expect(element).not.toBeNull();
  await act(async () => {
    element.value = String(id);
    element.dispatchEvent(new Event('change', {bubbles: true}));
  });
}
export async function travel(direction) {
  await act(async () => {
    fixture.cursor += direction === 'back' ? -1 : 1;
    const entry = fixture.entries[fixture.cursor];
    expect(entry).toBeDefined();
    fixture.replaceState(entry.state, '', entry.url);
    window.dispatchEvent(new PopStateEvent('popstate', {state: entry.state}));
  });
}
export async function visit(hash) {
  await act(async () => {
    window.history.pushState({}, '', `/${hash}`);
    window.dispatchEvent(new PopStateEvent('popstate', {state: window.history.state}));
  });
}
export async function clickNav(module) {
  await act(async () => document.querySelector(`button[data-nav="${module}"]`).click());
}
export const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return {promise, resolve};
};

// Same failure cases run against all three real pages, with real App navigation.
export function companyFailureCases({module, picker, endpoint, result, assertCompany}) {
  const dataCalls = () => fixture.api.mock.calls.filter(([path]) => module === 'customer_360' ? /^\/companies\/\d+\/status$/.test(path) : path.startsWith(endpoint('')));
  test.each(['0', '-1', '1.5', 'bogus', '999'])(`${module}: invalid/inaccessible deep link %s never requests company data`, async (id) => {
    await mount(`/#m=${module}&company=${id}`);
    expect(dataCalls().length).toBe(0);
    expect(sidebar()?.value).toBe('');
    expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
    expect(mainText()).not.toContain('Sistem yükleniyor');
  });
  test(`${module}: empty directory has a finite empty state`, async () => {
    fixture.companies = [];
    await mount(`/#m=${module}&company=174`);
    expect(sidebar()?.disabled).toBe(true);
    expect(document.body.textContent).toContain('erişilebilir');
    expect(dataCalls().length).toBe(0);
    expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
  });
  test(`${module}: directory error supports explicit retry without automatic retries`, async () => {
    fixture.overrides.set('/companies', new Error('Firma dizini hatası'));
    await mount(`/#m=${module}&company=174`);
    expect(document.body.textContent).toContain('Firma listesi yüklenemedi');
    expect(dataCalls().length).toBe(0);
    const count = calls('/companies').length;
    await act(async () => { await Promise.resolve(); });
    expect(calls('/companies').length).toBe(count);
    fixture.overrides.delete('/companies');
    await act(async () => [...document.querySelectorAll('button')].find((button) => button.textContent === 'Tekrar dene').click());
    await assertCompany(174);
  });
  test(`${module}: directory loading finishes and does not query company data early`, async () => {
    const pending = deferred();
    fixture.overrides.set('/companies', pending.promise);
    await mount(`/#m=${module}&company=174`);
    expect(sidebar()?.disabled).toBe(true);
    expect(document.body.textContent).toContain('Firmalar yükleniyor');
    expect(dataCalls().length).toBe(0);
    await act(async () => pending.resolve(companies));
    await assertCompany(174);
  });
  test(`${module}: data errors finish loading without retries or old data`, async () => {
    fixture.overrides.set(endpoint(174), new Error('Özet bağlantı hatası'));
    await mount(`/#m=${module}&company=174`);
    expect(mainText()).toContain('Özet bağlantı hatası');
    expect(calls(endpoint(174)).length).toBe(1);
    expect(mainText()).not.toContain('kayıtları yükleniyor');
  });
  test(`${module}: slow old response cannot overwrite a new company`, async () => {
    const pending = deferred();
    fixture.overrides.set(endpoint(174), pending.promise);
    await mount(`/#m=${module}&company=174`);
    await choose(sidebar(), 175);
    await assertCompany(175);
    await act(async () => pending.resolve(result(174)));
    await assertCompany(175);
  });
  test(`${module}: repeated selection does not add history or refetch`, async () => {
    await mount(`/#m=${module}&company=174`);
    await assertCompany(174);
    const count = calls(endpoint(174)).length;
    const index = window.history.state.navigationIndex;
    await choose(picker(), 174);
    await choose(sidebar(), 174);
    expect(window.history.state.navigationIndex).toBe(index);
    expect(calls(endpoint(174)).length).toBe(count);
  });
  test(`${module}: inaccessible company during history navigation clears the old data`, async () => {
    await mount(`/#m=${module}&company=174`);
    await visit(`#m=${module}&company=999`);
    expect(sidebar()?.value).toBe('');
    expect(calls(endpoint(999)).length).toBe(0);
    expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
  });
}
