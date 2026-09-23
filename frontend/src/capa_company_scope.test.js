import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, beforeEach, expect, test, vi} from 'vitest';
import {CapaPage} from './incidents';
import {api, downloadFile} from './api';

vi.mock('./api', () => ({api: vi.fn(), downloadFile: vi.fn()}));
let root;
const companies = [{id: 175, name: 'Diğer firma'}, {id: 174, name: 'Seçili firma'}];
const user = {id: 2, role: 'company_admin'};
const board = (id, name = 'Seçili DÖF') => ({
  company_id: id, summary: {total: 1, open: 1, overdue: 1, completed: 0},
  items: [{key: `r-${id}`, code: `D-${id}`, company_id: id, title: name, source: 'Risk', is_completed: false, is_overdue: true, status: 'Açık'}],
});
async function render(props) { await act(async () => root.render(React.createElement(CapaPage, {user, ...props}))); }

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.clearAllMocks();
  sessionStorage.clear();
  window.history.replaceState({}, '', '/#m=capa');
  document.body.innerHTML = '<div id="test-root"></div>';
  root = createRoot(document.querySelector('#test-root'));
  api.mockImplementation(async (path) => path === '/companies' ? companies : board(Number(new URLSearchParams(path.split('?')[1]).get('company_id'))));
});
afterEach(async () => { await act(async () => root.unmount()); vi.unstubAllGlobals(); });

test('requests only the explicitly selected company and scopes Excel identically', async () => {
  await render({companyId: '174'});
  expect(api).toHaveBeenCalledWith('/incidents/capa-board?company_id=174');
  expect(api.mock.calls.every(([path]) => path === '/companies' || path === '/incidents/capa-board?company_id=174')).toBe(true);
  expect(document.body.textContent).toContain('Seçili DÖF');
  expect(document.body.textContent).toContain('gecikmiş 1');
  expect(document.querySelector('[aria-label="DÖF firma / işyeri seçiniz"]').value).toBe('174');
  await act(async () => [...document.querySelectorAll('button')].find((button) => button.textContent.includes('Excel Rapor')).click());
  expect(downloadFile).toHaveBeenCalledWith('/incidents/capa-board.xlsx?company_id=174', expect.stringContaining('dof-panosu-174-'));
});

test('does not select the first company or query all firms when selection is empty', async () => {
  await render({companyId: ''});
  expect(api.mock.calls).toEqual([['/companies']]);
  expect(document.body.textContent).toContain('DÖF listesini görüntülemek için firma / işyeri seçiniz.');
  expect([...document.querySelectorAll('button')].find((button) => button.textContent.includes('Excel Rapor')).disabled).toBe(true);
});

test('fixed workplace accounts always use their own company', async () => {
  await render({user: {...user, company_id: 174}, companyId: '175'});
  expect(api).toHaveBeenCalledWith('/incidents/capa-board?company_id=174');
  expect(document.querySelector('[aria-label="DÖF firma / işyeri seçiniz"]')).toBeNull();
});

test('ignores slow responses for the previously selected company', async () => {
  let finishOld;
  api.mockImplementation((path) => {
    if (path === '/companies') return Promise.resolve(companies);
    if (path.endsWith('174')) return new Promise((resolve) => { finishOld = resolve; });
    return Promise.resolve(board(175, 'Yeni firmanın DÖF kaydı'));
  });
  await render({companyId: '174'});
  await render({companyId: '175'});
  await act(async () => finishOld(board(174, 'Eski firmanın DÖF kaydı')));
  expect(document.body.textContent).toContain('Yeni firmanın DÖF kaydı');
  expect(document.body.textContent).not.toContain('Eski firmanın DÖF kaydı');
});

test('shows API failures as failures instead of an empty DÖF list', async () => {
  api.mockImplementation(async (path) => { if (path === '/companies') return companies; throw new Error('Bağlantı hatası'); });
  await render({companyId: '174'});
  expect(document.querySelector('[role="alert"]').textContent).toContain('Bağlantı hatası');
  expect(document.body.textContent).not.toContain('Bu firmada kayıtlı DÖF bulunmuyor.');
});
