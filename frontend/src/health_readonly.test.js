// @vitest-environment happy-dom
import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, expect, it, vi} from 'vitest';
import {HealthPage} from './health';
vi.mock('./api', () => ({API_URL: '', api: vi.fn(async (path) => {
  if (path === '/companies') return [{id: 3, name: 'Firma'}];
  if (path.startsWith('/employees')) return [{id: 4, company_id: 3, full_name: 'Ali Test'}];
  if (path.startsWith('/health-records?')) return [{id: 5, company_id: 3, employee_id: 4, employee_name: 'Ali Test', confidential_note: 'Gizli klinik not', summary: 'Muayene sonucu', fitness_status: 'fit', has_report: true}];
  return {};
}), downloadFile: vi.fn(), uploadFile: vi.fn()}));
let root, host;
afterEach(async () => { if(root) await act(async () => root.unmount()); host?.remove(); });
it('lets a workplace manager read details and download without mutation controls', async () => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
  await act(async () => root.render(React.createElement(HealthPage, {user:{role:'company_admin', company_id:3, email:'manager@test.com'}})));
  expect(host.textContent).toContain('Ali Test');
  const buttons = () => [...host.querySelectorAll('button')];
  expect(buttons().some(x => /Yeni Kayıt|Düzenle|^Sil$/.test(x.textContent))).toBe(false);
  expect(buttons().some(x => x.textContent.includes('Rapor'))).toBe(true);
  const detail = buttons().find(x => x.textContent.includes('Ayrıntılar'));
  expect(detail).toBeTruthy();
  await act(async () => detail.click());
  expect(document.body.textContent).toContain('Gizli klinik not');
  expect(document.querySelector('input[type="file"]')).toBeNull();
  expect([...document.querySelectorAll('button')].some(x => /Kaydet/.test(x.textContent))).toBe(false);
});
