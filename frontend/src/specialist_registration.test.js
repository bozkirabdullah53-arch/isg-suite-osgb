import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {api} from './api';
import {SpecialistRegisterPage} from './eisa';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

vi.mock('./api', () => ({api: vi.fn(), downloadFile: vi.fn(), API_URL: '/api/v1'}));

let container;
let root;

beforeEach(() => {
  api.mockReset();
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

function field(label) {
  return [...container.querySelectorAll('label.field')]
    .find((element) => element.querySelector('span')?.textContent === label)
    ?.querySelector('input, select');
}

function fill(label, value) {
  const input = field(label);
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  act(() => {
    setter.call(input, value);
    input.dispatchEvent(new Event('input', {bubbles: true}));
  });
}

it('submits an individual application without a certificate number', async () => {
  const result = {access_token: 'registration-token'};
  api.mockResolvedValue(result);
  const onRegistered = vi.fn();
  act(() => root.render(React.createElement(SpecialistRegisterPage, {onRegistered})));

  expect(container.textContent).not.toContain('Sertifika no');
  expect(field('Sertifika sınıfı *').value).toBe('C');
  fill('Ad soyad *', 'Ahmet Yilmaz');
  fill('E-posta *', 'individual@example.com');
  fill('Şifre *', 'IndividualPass123!');
  fill('Şifre tekrar *', 'IndividualPass123!');
  for (const checkbox of container.querySelectorAll('input[type="checkbox"]')) {
    act(() => checkbox.click());
  }
  expect(container.querySelector('form').checkValidity()).toBe(true);

  await act(async () => {
    container.querySelector('form').dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
  });

  expect(api).toHaveBeenCalledTimes(1);
  const [path, options] = api.mock.calls[0];
  expect(path).toBe('/auth/register');
  expect(options.method).toBe('POST');
  expect(JSON.parse(options.body)).toEqual({
    full_name: 'Ahmet Yilmaz',
    email: 'individual@example.com',
    phone: '',
    certificate_class: 'C',
    password: 'IndividualPass123!',
    password_confirm: 'IndividualPass123!',
    contract_accepted: true,
    personal_data_accepted: true,
  });
  expect(onRegistered).toHaveBeenCalledWith(result);
});
