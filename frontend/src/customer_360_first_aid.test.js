import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, beforeEach, expect, test, vi} from 'vitest';
import {api} from './api';
import {Customer360Page} from './customer_360';

vi.mock('./api', () => ({api: vi.fn(), downloadFile: vi.fn()}));
vi.mock('./workplace_obligation_center', () => ({WorkplaceObligationCenter: () => null}));

let root;
let onNavigate;
let payload;

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  sessionStorage.clear();
  document.body.innerHTML = '<div id="root"></div>';
  root = createRoot(document.querySelector('#root'));
  onNavigate = vi.fn();
  payload = {
    company: {id: 174, name: 'Test İşyeri'}, counts: {}, compliance: {}, alerts: [],
    status_center: {items: []},
    first_aid: {
      hazard_known: true, hazard_class: 'Çok Tehlikeli', active_employee_count: 88,
      required_count: 9, assigned_primary_count: 9, assigned_reserve_count: 0,
      assignment_missing_count: 0, assignment_complete: true, valid_count: 0,
      missing_count: 9, incomplete_count: 9, expired_count: 0, expiring_soon_count: 0,
      future_missing_count: 9,
    },
    first_aid_people: [{employee_id: 1, name: 'Görevlendirilen Çalışan', membership: 'asil',
                       status: 'incomplete', certificate_no: null, end_date: null}],
  };
  api.mockImplementation(async () => payload);
});

afterEach(async () => {
  await act(async () => root.unmount());
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

async function mount() {
  await act(async () => root.render(React.createElement(Customer360Page, {
    companyId: 174, onNavigate, canOpenModule: () => true,
  })));
  return [...document.querySelectorAll('section.panel')]
    .find((panel) => panel.querySelector('h3')?.textContent === 'İlkyardımcı Yeterliliği');
}

test('completed assignments stay visible while certificate information is missing', async () => {
  const panel = await mount();
  expect(panel.textContent).toContain('Görevlendirmeler tamamlandı (9/9 asıl)');
  expect(panel.textContent).toContain('Belge bilgisi eksik: 9');
  expect(panel.textContent).toContain('İlkyardımcı belge bilgileri tamamlanmalı');
  expect(panel.textContent).not.toContain('Mevzuata uygun değil');
  expect(panel.querySelector('tbody').textContent).toContain('Görevlendirilen Çalışan');
  expect(panel.querySelector('tbody').textContent).toContain('Asıl');
  await act(async () => panel.querySelector('button').click());
  expect(onNavigate).toHaveBeenCalledWith('acil_ekipler', {companyId: '174', recordTarget: null});
  expect(sessionStorage.getItem('isg_status_company_id')).toBe('174');
});

test('valid certificates complete the certificate check while expired certificates keep it open', async () => {
  Object.assign(payload.first_aid, {valid_count: 9, missing_count: 0, incomplete_count: 0,
                                    future_missing_count: 0});
  payload.first_aid_people[0].status = 'valid';
  const panel = await mount();
  expect(panel.textContent).toContain('Geçerli belgeli ilkyardımcı sayısı yeterli');
  expect(panel.textContent).not.toContain('belge bilgileri tamamlanmalı');

  Object.assign(payload.first_aid, {valid_count: 8, missing_count: 1, expired_count: 1});
  payload.first_aid_people[0].status = 'expired';
  await act(async () => [...document.querySelectorAll('button')]
    .find((button) => button.textContent.trim() === 'Yenile').click());
  expect(panel.textContent).toContain('Görevlendirmeler tamamlandı (9/9 asıl)');
  expect(panel.textContent).toContain('İlkyardımcı belge bilgileri tamamlanmalı');
  expect(panel.querySelector('tbody').textContent).toContain('Süresi dolmuş');
});

test('an empty workplace does not claim completed first aid assignments', async () => {
  payload.first_aid.active_employee_count = 0;
  const panel = await mount();
  expect(panel.textContent).toContain('Aktif çalışan kaydı yok');
  expect(panel.textContent).not.toContain('Görevlendirmeler tamamlandı');
});
