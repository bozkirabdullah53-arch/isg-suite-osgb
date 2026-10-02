import {act} from 'react';
import {afterEach, expect, test, vi} from 'vitest';
import {clearAccessToken, setAccessToken} from './auth_session';
import {calls, choose, fixture, mount} from './navigation_app_fixture';

const professionals = [
  {id: 11, full_name: 'Test Uzman', professional_type: 'safety_specialist'},
  {id: 12, full_name: 'Test Hekim', professional_type: 'workplace_physician'},
];

afterEach(() => clearAccessToken());

function field(label) {
  return [...document.querySelectorAll('[role="dialog"] label')]
    .find(node => node.querySelector('span')?.textContent === label)
    ?.querySelector('select, input');
}

async function openAssignment(theme) {
  fixture.overrides.set('/osgb/professionals?osgb_id=4', professionals);
  fixture.overrides.set('/osgb/assignments', []);
  fixture.overrides.set('/osgb/capacity?osgb_id=4', {
    professionals: professionals.map(pro => ({professional_id: pro.id, capacity_used_minutes: 600, capacity_remaining_minutes: 11100})),
    workplaces: [],
  });
  fixture.overrides.set('/osgb/katip-prep?osgb_id=4', {});
  await mount('/#m=assignments', {theme});
  await act(async () => [...document.querySelectorAll('button')].find(button => button.textContent.includes('Görevlendirme Yap')).click());
  return document.querySelector('[role="dialog"]');
}

async function flushCompanyChange() {
  await act(async () => { await new Promise(resolve => window.setTimeout(resolve, 0)); });
}

async function fill(label, value) {
  const input = field(label);
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event('input', {bubbles: true}));
    input.dispatchEvent(new Event('change', {bubbles: true}));
  });
}

for (const theme of ['classic', 'modern']) {
  test.each(professionals)(`Görevlendirme: $professional_type seçimi formu ve firma kapsamını korur (${theme})`, async pro => {
    const dialog = await openAssignment(theme);
    expect(dialog).not.toBeNull();
    await choose(field('Profesyonel'), pro.id);
    await flushCompanyChange();

    expect(document.querySelector('[role="dialog"]')).toBe(dialog);
    expect(field('Profesyonel')?.value).toBe(String(pro.id));
    expect(dialog.textContent).toContain(`${pro.full_name} aylık kapasitesi`);
    expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
    expect(window.location.hash).toBe('#m=assignments');
    expect(calls('/osgb/assignments')).toHaveLength(1);
  });

  test(`Görevlendirme: formdaki işyeri seçimi profesyonel seçimini sıfırlamaz (${theme})`, async () => {
    const dialog = await openAssignment(theme);
    await choose(field('Profesyonel'), professionals[0].id);
    await flushCompanyChange();
    await choose(field('İşyeri'), 174);
    await flushCompanyChange();

    expect(document.querySelector('[role="dialog"]')).toBe(dialog);
    expect(field('İşyeri')?.value).toBe('174');
    expect(field('Profesyonel')?.value).toBe(String(professionals[0].id));
    expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
    expect(calls('/osgb/assignments')).toHaveLength(1);
  });
}

test.each(professionals)('Görevlendirme: $professional_type doğru işyeri, görev ve sözleşmeyle kaydedilir', async pro => {
  const dialog = await openAssignment('modern');
  await fill('Başlangıç', '2026-10-02');
  await fill('İSG-KATİP Sözleşme No', 'TEST-KATIP-001');
  const file = new File(['%PDF-1.4\nTest contract'], 'test-sozlesme.pdf', {type: 'application/pdf'});
  await act(async () => {
    const input = field('Sözleşme Dosyası (pdf / jpg / png)');
    Object.defineProperty(input, 'files', {configurable: true, value: [file]});
    input.dispatchEvent(new Event('change', {bubbles: true}));
  });
  await choose(field('İşyeri'), 174);
  await flushCompanyChange();
  await choose(field('Profesyonel'), pro.id);
  await flushCompanyChange();

  expect(document.querySelector('[role="dialog"]')).toBe(dialog);
  expect(field('Başlangıç')?.value).toBe('2026-10-02');
  expect(field('İSG-KATİP Sözleşme No')?.value).toBe('TEST-KATIP-001');
  expect(dialog.textContent).toContain(file.name);
  const created = {id: 99, company_id: 174, professional_id: pro.id, professional_type: pro.professional_type,
    start_date: '2026-10-02', status: 'active', contract_file_name: file.name};
  let saved = false;
  fixture.overrides.set('/osgb/assignments', options => {
    if (options.method === 'POST') {saved = true; return created;}
    return saved ? [created] : [];
  });
  const previousFetch = globalThis.fetch;
  // The fixture's placeholder token has no expiry; the real upload helper
  // needs an unexpired test token so this scenario does not enter refresh.
  const payload = btoa(JSON.stringify({exp: Math.floor(Date.now() / 1000) + 3600})).replace(/=+$/, '');
  setAccessToken(`e30.${payload}.test-signature`);
  const network = vi.fn(async (url, options) => {
    if (String(url).endsWith('/live')) return new Response(null, {status: 204});
    if (String(url).endsWith('/osgb/assignments/99/contract')) {
      return new Response(JSON.stringify(created), {headers: {'Content-Type': 'application/json'}});
    }
    return previousFetch(url, options);
  });
  vi.stubGlobal('fetch', network);
  await act(async () => dialog.querySelector('form').dispatchEvent(new Event('submit', {bubbles: true, cancelable: true})));
  await flushCompanyChange();

  const writes = calls('/osgb/assignments').filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(1);
  expect(JSON.parse(writes[0][1].body)).toMatchObject({
    osgb_id: 4, company_id: 174, professional_id: pro.id, professional_type: pro.professional_type,
    start_date: '2026-10-02', isg_katip_contract_number: 'TEST-KATIP-001',
  });
  const uploads = network.mock.calls.filter(([url]) => String(url).endsWith('/osgb/assignments/99/contract'));
  expect(uploads).toHaveLength(1);
  expect(uploads[0][1].method).toBe('POST');
  expect(uploads[0][1].body.get('file').name).toBe(file.name);
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  expect(document.querySelector('.assignments-table')?.textContent).toContain(pro.full_name);
  expect(sessionStorage.getItem('isg_selected_company_id')).toBeNull();
});
