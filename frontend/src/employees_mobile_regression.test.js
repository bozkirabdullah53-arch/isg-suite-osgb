import {act} from 'react';
import {beforeEach, expect, test, vi} from 'vitest';
import {fixture, mount, choose, calls, deferred} from './navigation_app_fixture';

const rows = [
  {id: 1, company_id: 176, branch_id: 11, full_name: 'Ayşe Test', is_active: true},
  {id: 2, company_id: 176, branch_id: 12, full_name: 'Mehmet Test', is_active: true},
  {id: 3, company_id: 176, branch_id: 11, full_name: 'Arşiv Test', is_active: false},
];
const picker = (label) => Array.from(document.querySelectorAll('.employees-filters label')).find((el) => el.textContent.startsWith(label))?.querySelector('select');
const button = (text, root = document) => Array.from(root.querySelectorAll('button')).find((el) => el.textContent === text);
const click = async (el) => { expect(el).toBeTruthy(); await act(async () => el.click()); };

beforeEach(() => {
  fixture.user = {...fixture.user, role: 'safety_specialist'};
  fixture.overrides.set('/branches', [{id: 11, company_id: 176, name: 'Üretim'}, {id: 12, company_id: 176, name: 'Depo'}]);
  fixture.overrides.set('/employees?company_id=176&active=true', rows);
  fixture.overrides.set('/employees?company_id=176&active=true&branch_id=11', rows);
  fixture.overrides.set('/employees?company_id=176&active=true&branch_id=12', rows);
  vi.spyOn(window, 'alert').mockImplementation(() => {});
});

test('branch filtering reloads the API and restricts bulk selection to visible active employees', async () => {
  await mount('/#m=employees');
  await choose(picker('Şube filtresi'), 11);
  expect(calls('/employees').at(-1)[0]).toBe('/employees?company_id=176&active=true&branch_id=11');
  expect(document.querySelectorAll('.employee-card')).toHaveLength(1);
  expect(document.querySelector('.employee-card').textContent).toContain('Ayşe Test');
  await click(button('Görünenlerin Tümünü Seç'));
  expect(button('Seçilenleri Kalıcı Sil (1)')).toBeTruthy();
  await choose(picker('Şube filtresi'), 12);
  expect(button('Seçilenleri Kalıcı Sil (1)')).toBeUndefined();
  expect(document.querySelector('.employee-card').textContent).toContain('Mehmet Test');
});

test('an older company-wide response cannot replace the latest branch response', async () => {
  const old = deferred();
  fixture.overrides.set('/employees?company_id=176&active=true', () => old.promise);
  await mount('/#m=employees');
  await choose(picker('Şube filtresi'), 12);
  await act(async () => old.resolve([rows[0]]));
  expect(document.querySelectorAll('.employee-card')).toHaveLength(1);
  expect(document.querySelector('.employee-card').textContent).toContain('Mehmet Test');
});

test('a failed employee request clears stale data and offers a retry', async () => {
  fixture.overrides.set('/employees?company_id=176&active=true&branch_id=11', new Error('Bağlantı hatası'));
  await mount('/#m=employees');
  await choose(picker('Şube filtresi'), 11);
  expect(document.querySelector('.employees-list-error').textContent).toContain('Bağlantı hatası');
  expect(document.querySelectorAll('.employee-card')).toHaveLength(0);
  fixture.overrides.set('/employees?company_id=176&active=true&branch_id=11', rows);
  await click(button('Tekrar Dene'));
  expect(document.querySelector('.employees-list-error')).toBeNull();
  expect(document.querySelectorAll('.employee-card')).toHaveLength(1);
});

test('a pending save disables submit and suppresses a second submission', async () => {
  const saved = deferred();
  fixture.overrides.set('/employees', () => saved.promise);
  await mount('/#m=employees');
  await click(document.querySelector('[data-ai-action="employee.create"]'));
  const form = document.querySelector('.modal form');
  await act(async () => {
    form.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
    form.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
  });
  const save = form.querySelector('[type="submit"]');
  expect(save.disabled).toBe(true);
  expect(save.textContent).toBe('Kaydediliyor…');
  expect(calls('/employees').filter(([path, options]) => path === '/employees' && options.method === 'POST')).toHaveLength(1);
  await act(async () => saved.resolve({id: 4}));
  expect(document.querySelector('.modal')).toBeNull();
  expect(document.body.style.overflow).not.toBe('hidden');
});

test('archive view and optional employee actions remain available', async () => {
  fixture.overrides.set('/employees?company_id=176&active=false', rows);
  await mount('/#m=employees');
  await choose(picker('Personel görünümü'), 'inactive');
  const card = document.querySelector('.employee-card');
  expect(card.textContent).toContain('Arşiv Test');
  expect(button('Aktifleştir', card)).toBeTruthy();
  expect(button('Pasife Al', card)).toBeUndefined();
  expect(document.querySelector('.employees-tools').open).toBe(false);
  expect(document.querySelector('.employees-import-help').open).toBe(false);
});
