import {act} from 'react';
import {expect, test, vi} from 'vitest';
import {board, calls, choose, companyFailureCases, fixture, mainText, mount, routeCompany, sidebar, travel, visit} from './navigation_app_fixture';

const picker = () => document.querySelector('[aria-label="DÖF firma / işyeri seçiniz"]');
async function assertCompany(id) {
  await vi.waitFor(() => {
    expect(mainText()).toContain(`DÖF-${id}`);
    expect(sidebar()?.value).toBe(String(id));
    expect(picker()?.value).toBe(String(id));
    expect(routeCompany()).toBe(String(id));
    expect(sessionStorage.getItem('isg_selected_company_id')).toBe(String(id));
  });
}

test('DÖF: deep link, both selectors, recorded Back/Forward, clearing and status-center link', async () => {
  await mount('/#m=capa&company=174');
  await assertCompany(174);
  const initialIndex = window.history.state.navigationIndex;
  await choose(sidebar(), 175);
  await assertCompany(175);
  expect(mainText()).not.toContain('DÖF-174');
  expect(window.history.state.navigationIndex).toBe(initialIndex + 1);
  await choose(picker(), 176);
  await assertCompany(176);
  await travel('back');
  await assertCompany(175);
  await travel('back');
  await assertCompany(174);
  await travel('forward');
  await assertCompany(175);
  await choose(picker(), '');
  expect(mainText()).not.toContain('DÖF-175');
  expect(mainText()).toContain('DÖF listesini görüntülemek için firma / işyeri seçiniz.');
  expect(routeCompany()).toBeNull();
  expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
  await travel('back');
  await assertCompany(175);
  await travel('forward');
  expect(picker()?.value).toBe('');
  await visit('#m=workplace_status&company=175');
  await choose(sidebar(), 176);
  await vi.waitFor(() => expect(document.querySelector('.customer-360-page h2')?.textContent).toContain('Üçüncü Test Firması'));
  const rows = [...document.querySelectorAll('.customer-360-page tr')];
  const dofRow = rows.find((row) => row.textContent.includes('Düzeltici ve önleyici faaliyetler'));
  expect(rows.find((row) => row.textContent.includes('Risk kaydı')).querySelector('button')).toBeNull();
  await act(async () => dofRow.querySelector('button').click());
  await assertCompany(176);
  await act(async () => document.querySelector('[aria-label="DÖF-176 kaydını aç"]').click());
  expect(document.querySelector('[role="dialog"]')).not.toBeNull();
  expect(document.querySelector('[role="dialog"] fieldset').disabled).toBe(true);
  expect(fixture.api.mock.calls.some(([path]) => path === '/incidents')).toBe(false);
});

test('DÖF: empty deep link offers a picker without an unscoped request', async () => {
  await mount('/#m=capa');
  expect(window.location.hash).toBe('#m=capa');
  expect(picker()?.value).toBe('');
  expect(mainText()).toContain('DÖF listesini görüntülemek için firma / işyeri seçiniz.');
  expect(calls('/incidents')).toHaveLength(0);
});

test('DÖF: a fixed workplace account cannot override its own company through the URL', async () => {
  fixture.user = {...fixture.user, company_id: 174};
  await mount('/#m=capa&company=175');
  expect(mainText()).toContain('DÖF-174');
  expect(mainText()).not.toContain('DÖF-175');
  expect(routeCompany()).toBe('174');
  expect(picker()).toBeNull();
  expect(calls('/incidents/capa-board?company_id=175')).toHaveLength(0);
});

companyFailureCases({module: 'capa', picker, endpoint: (id) => `/incidents/capa-board?company_id=${id}`, result: board, assertCompany});
