// @vitest-environment happy-dom
import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, expect, test, vi} from 'vitest';
import {LoginCaptcha} from './login_captcha';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let root;
afterEach(async () => {
  if (root) await act(async () => root.unmount());
  root = null;
  delete window.turnstile;
  document.body.innerHTML = '';
});

test('a solved, expired and failed challenge updates the login token', async () => {
  let callbacks;
  window.turnstile = {
    ready: fn => fn(),
    render: (_el, opts) => {callbacks = opts; return 'widget';},
    remove: () => {},
  };
  const host = document.createElement('div');
  document.body.append(host);
  const tokens = [];
  const errors = [];
  root = createRoot(host);
  await act(async () => root.render(React.createElement(LoginCaptcha, {siteKey: "public", onToken: t => tokens.push(t), onError: e => errors.push(e)})));
  expect(callbacks.action).toBe('login');
  await act(async () => callbacks.callback('one-use-token'));
  expect(tokens.at(-1)).toBe('one-use-token');
  await act(async () => callbacks['expired-callback']());
  expect(tokens.at(-1)).toBe('');
  await act(async () => callbacks['error-callback']());
  expect(tokens.at(-1)).toBe('');
  expect(errors.at(-1)).toMatch(/doğrulama/i);
});

test('a retry invalidates the old solution and mounts a fresh challenge', async () => {
  const callbacks = [];
  window.turnstile = {
    ready: fn => fn(),
    render: (_el, opts) => {callbacks.push(opts); return String(callbacks.length);},
    remove: () => {},
  };
  const host = document.createElement('div');
  document.body.append(host);
  const onToken = vi.fn();
  root = createRoot(host);
  await act(async () => root.render(React.createElement(LoginCaptcha, {siteKey: "public", resetKey: 0, onToken})));
  await act(async () => callbacks[0].callback('old-token'));
  await act(async () => root.render(React.createElement(LoginCaptcha, {siteKey: "public", resetKey: 1, onToken})));
  expect(onToken.mock.lastCall).toEqual(['']);
  await act(async () => callbacks[1].callback('new-token'));
  expect(onToken.mock.lastCall).toEqual(['new-token']);
});
