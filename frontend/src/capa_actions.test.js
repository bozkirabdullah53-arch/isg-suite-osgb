import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, beforeEach, expect, test, vi} from 'vitest';
import {CapaPage} from './incidents';
import {api} from './api';
import {canManageDof, capaStatus} from './capa_actions';
import {PROFESSIONAL_MENU_MODULES} from './professional_navigation';

vi.mock('./api', () => ({api: vi.fn(), downloadFile: vi.fn()}));
let root;
let completed;
const row = {id: 7, key: 'r-7', source_type: 'risk', source: 'Risk', parent_id: 11,
  company_id: 174, code: 'DÖF-XLS-test', parent: 'R-11', title: 'Makine koruyucusunu tamamla',
  responsible: 'Bakım sorumlusu', term: '2026-06-12', term_kind: 'date',
  source_term: 'Derhal / En geç 3 gün', status: 'Açık', is_overdue: true, is_completed: false};
const workplace = {id: 1, role: 'company_admin', company_id: 174, full_name: 'İşyeri Yetkilisi'};
async function render(user = workplace, companyId = '174') {
  await act(async () => root.render(React.createElement(CapaPage, {user, companyId})));
}
async function click(text) {
  await act(async () => [...document.querySelectorAll('button')].find((button) => button.textContent === text).click());
}
async function fill(label, value) {
  await act(async () => {
    const element = document.querySelector(`[aria-label="${label}"]`);
    const prototype = element.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, value);
    element.dispatchEvent(new Event('input', {bubbles: true}));
    element.dispatchEvent(new Event('change', {bubbles: true}));
  });
}
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.clearAllMocks(); completed = false;
  document.body.innerHTML = '<div id="test-root"></div>';
  root = createRoot(document.querySelector('#test-root'));
  api.mockImplementation(async (path, options) => {
    if (path === '/companies') return [{id: 174, name: 'İşyeri'}];
    if (options?.method === 'POST') { completed = true; return {}; }
    if (options?.method === 'PATCH') return {};
    return {company_id: 174, summary: {total: 1, open: completed ? 0 : 1, overdue: completed ? 0 : 1, completed: completed ? 1 : 0},
      items: [{...row, is_completed: completed, is_overdue: !completed}]};
  });
});
afterEach(async () => { await act(async () => root.unmount()); vi.unstubAllGlobals(); });

test('OSGB manager is read-only; workplace, specialist and physician may manage DÖFs', async () => {
  expect(canManageDof({role: 'company_admin'})).toBe(false);
  expect(canManageDof(workplace)).toBe(true);
  expect(canManageDof({role: 'safety_specialist'})).toBe(true);
  expect(canManageDof({role: 'workplace_physician'})).toBe(true);
  expect(canManageDof({role: 'other_health_personnel'})).toBe(false);
  expect(PROFESSIONAL_MENU_MODULES.workplace_physician).toContain('capa');
  await render({role: 'company_admin', id: 9});
  await click(row.code);
  expect(document.querySelector('[role="dialog"]')).not.toBeNull();
  expect(document.querySelector('fieldset').disabled).toBe(true);
  expect(document.body.textContent).not.toContain('DÖF’ü tamamla');
});

test('opens the selected DÖF, saves only changed fields, and refreshes the selected firm', async () => {
  await render(); await click(row.code);
  expect(document.querySelector('[role="dialog"]').textContent).toContain('Derhal / En geç 3 gün');
  await fill('DÖF sorumlusu', 'Üretim müdürü');
  await click('Değişiklikleri kaydet');
  expect(api).toHaveBeenCalledWith('/risks/11/dofs/7', {method: 'PATCH', body: JSON.stringify({responsible_person: 'Üretim müdürü'})});
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  expect(api.mock.calls.filter(([path]) => path.includes('capa-board'))).toHaveLength(2);
});

test('completing a DÖF records its date/note and removes overdue status', async () => {
  await render(); await click(row.code); await click('DÖF’ü tamamla');
  await fill('Kapanış notu', 'Makine koruyucusu takıldı ve kontrol edildi.');
  await fill('Tamamlanma tarihi', '2026-06-11');
  await click('Tamamlandı olarak kaydet');
  expect(api).toHaveBeenCalledWith('/risks/11/dofs/7/complete', {method: 'POST', body: JSON.stringify({completion_date: '2026-06-11', completion_note: 'Makine koruyucusu takıldı ve kontrol edildi.'})});
  expect(document.body.textContent).toContain('gecikmiş 0');
  expect(document.querySelector('.badge-danger')).toBeNull();
  expect(document.querySelector('.badge-ok').textContent).toBe('Tamamlandı');
});

test('failed writes keep the dialog and error visible', async () => {
  await render(); await click(row.code);
  await fill('DÖF sorumlusu', 'Üretim müdürü');
  api.mockRejectedValueOnce(new Error('Kaydetme başarısız'));
  await click('Değişiklikleri kaydet');
  expect(document.querySelector('[role="dialog"]')).not.toBeNull();
  expect(document.querySelector('[role="alert"]').textContent).toContain('Kaydetme başarısız');
});

test('changing company closes the previous firm action form', async () => {
  const user = {role: 'workplace_physician', id: 4};
  await render(user); await click(row.code); await render(user, '175');
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  expect(api.mock.calls.some(([, options]) => options?.method === 'PATCH')).toBe(false);
});

test('continuous monitoring and unknown deadlines stay distinct from overdue and completed', () => {
  expect(capaStatus({term_kind: 'continuous'}).label).toBe('Sürekli izleme');
  expect(capaStatus({term_kind: 'unset'}).label).toBe('Termin belirlenmedi');
  expect(capaStatus({is_completed: true, is_overdue: true}).label).toBe('Tamamlandı');
});
