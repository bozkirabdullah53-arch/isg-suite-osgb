import React, {act, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, beforeEach, expect, test, vi} from 'vitest';
import {AppModal} from './ui_modal';

let root;
let trigger;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  document.body.innerHTML = '<button id="trigger">Aç</button><div id="root"></div>';
  document.body.style.overflow = 'auto';
  trigger = document.getElementById('trigger');
  trigger.focus();
  root = createRoot(document.getElementById('root'));
});
afterEach(async () => {
  await act(async () => root.unmount());
  document.body.innerHTML = '';
  document.body.style.overflow = '';
  vi.unstubAllGlobals();
});
const render = async (content) => act(async () => root.render(content));
const key = async (key, shiftKey = false) => act(async () => document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key, shiftKey, bubbles: true, cancelable: true})));

test('a dialog has a name, focuses its first field and restores the trigger', async () => {
  await render(React.createElement(AppModal, {title: 'Yeni Personel', close: () => {}}, React.createElement('input', {'aria-label': 'Ad Soyad'})));
  const dialog = document.querySelector('[role="dialog"]');
  expect(document.getElementById(dialog.getAttribute('aria-labelledby')).textContent).toBe('Yeni Personel');
  expect(document.activeElement).toBe(dialog.querySelector('input'));
  expect(document.body.style.overflow).toBe('hidden');
  await render(null);
  expect(document.activeElement).toBe(trigger);
  expect(document.body.style.overflow).toBe('auto');
  expect(document.body.hasAttribute('data-dialog-open')).toBe(false);
});

test('Tab wraps around enabled controls and focus cannot leave the dialog', async () => {
  await render(React.createElement(AppModal, {title: 'Düzenle', close: () => {}}, [
    React.createElement('input', {key: 'input'}),
    React.createElement('button', {key: 'last'}, 'Kaydet'),
    React.createElement('button', {key: 'disabled', disabled: true}, 'Bekleyin'),
  ]));
  const dialog = document.querySelector('[role="dialog"]');
  const close = dialog.querySelector('header button');
  const last = Array.from(dialog.querySelectorAll('button')).find((el) => el.textContent === 'Kaydet');
  last.focus();
  await key('Tab');
  expect(document.activeElement).toBe(close);
  await key('Tab', true);
  expect(document.activeElement).toBe(last);
  trigger.focus();
  expect(document.activeElement).toBe(dialog.querySelector('input'));
});

test('closed detail content is excluded from the focus loop but its summary remains focusable', async () => {
  await render(React.createElement(AppModal, {title: 'İşlemler', close: () => {}}, React.createElement('details', {}, [
    React.createElement('summary', {key: 'summary'}, 'Diğer'),
    React.createElement('input', {key: 'input'}),
  ])));
  const summary = document.querySelector('.modal summary');
  summary.focus();
  await key('Tab');
  expect(document.activeElement).toBe(document.querySelector('.modal header button'));
});

test('closing the top dialog preserves the parent scroll lock and focus', async () => {
  function Nested() {
    const [child, setChild] = useState(false);
    return React.createElement(AppModal, {title: 'Ana pencere', close: () => {}}, [
      React.createElement('button', {key: 'open', onClick: () => setChild(true)}, 'Alt pencereyi aç'),
      child && React.createElement(AppModal, {key: 'child', title: 'Alt pencere', close: () => setChild(false)}, React.createElement('input')),
    ]);
  }
  await render(React.createElement(Nested));
  const open = Array.from(document.querySelectorAll('.modal button')).find((el) => el.textContent === 'Alt pencereyi aç');
  open.focus();
  await act(async () => open.click());
  expect(document.querySelectorAll('[role="dialog"]')).toHaveLength(2);
  await key('Escape');
  expect(document.querySelectorAll('[role="dialog"]')).toHaveLength(1);
  expect(document.activeElement).toBe(open);
  expect(document.body.style.overflow).toBe('hidden');
  await render(null);
  expect(document.body.style.overflow).toBe('auto');
});
