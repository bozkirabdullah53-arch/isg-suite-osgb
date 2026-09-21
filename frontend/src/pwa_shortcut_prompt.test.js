import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {PwaShortcutPrompt} from './pwa_shortcut_prompt';
import {PWA_SHORTCUT_STORAGE_KEY as KEY} from './pwa_shortcut_prompt_logic';

let root;
const mount = async () => {
  const host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root.render(React.createElement(PwaShortcutPrompt)));
};
const click = async (text) => {
  const button = [...document.querySelectorAll('button')].find(b => b.textContent === text);
  expect(button).toBeTruthy();
  await act(async () => button.click());
};
beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  localStorage.clear();
  delete window.__isgDeferredInstallPrompt;
  vi.stubGlobal('matchMedia', query => ({matches: query.includes('max-width')}));
});
afterEach(async () => {
  if (root) await act(async () => root.unmount());
  document.body.innerHTML = '';
  vi.unstubAllGlobals();
});
describe('shortcut installation recovery', () => {
  it('asks again after a legacy acceptance that never installed', async () => {
    localStorage.setItem(KEY, 'accepted');
    await mount();
    expect(document.querySelector('[role="dialog"]')).not.toBeNull();
  });
  it('allows a dismissed prompt to be reopened without clearing site data', async () => {
    localStorage.setItem(KEY, 'dismissed');
    await mount();
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    await click('Ana ekrana ekle');
    expect(document.querySelector('[role="dialog"]')).not.toBeNull();
  });
  it('does not record reading manual instructions as an installed app', async () => {
    await mount();
    await click('Evet');
    expect(document.body.textContent).toContain('Tarayıcı menüsünden');
    expect(localStorage.getItem(KEY)).not.toBe('accepted');
    expect(localStorage.getItem(KEY)).not.toBe('installed');
  });
  it('handles rejected native prompts and clears the single-use event', async () => {
    window.__isgDeferredInstallPrompt = {prompt: () => Promise.reject(new Error('unavailable'))};
    await mount();
    await click('Evet');
    expect(document.body.textContent).toContain('Tarayıcı menüsünden');
    expect(window.__isgDeferredInstallPrompt).toBeNull();
  });
  it('uses a late native event and records installation only when confirmed', async () => {
    await mount();
    const event = new Event('beforeinstallprompt', {cancelable: true});
    event.prompt = vi.fn(async () => {});
    event.userChoice = Promise.resolve({outcome: 'accepted'});
    await act(async () => window.dispatchEvent(event));
    await click('Evet');
    expect(event.prompt).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem(KEY)).not.toBe('installed');
    await act(async () => window.dispatchEvent(new Event('appinstalled')));
    expect(localStorage.getItem(KEY)).toBe('installed');
    expect(document.body.textContent).toBe('');
    expect(window.__isgDeferredInstallPrompt).toBeNull();
  });
  it('hides installation UI when running standalone', async () => {
    vi.stubGlobal('matchMedia', query => ({matches: query.includes('standalone')}));
    await mount();
    expect(document.body.textContent).toBe('');
  });
});
