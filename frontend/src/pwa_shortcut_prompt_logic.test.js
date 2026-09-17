import {describe, expect, it} from 'vitest';

import {
  isIosDevice,
  isMobileViewport,
  isStandaloneDisplay,
  readShortcutChoice,
  shouldAskShortcutPrompt,
  shortcutInstructionText,
  writeShortcutChoice,
} from './pwa_shortcut_prompt_logic';

function fakeWindow({standalone = false, ua = 'Android', maxWidth = true, coarse = true} = {}) {
  return {
    navigator: {userAgent: ua, standalone, platform: 'Linux', maxTouchPoints: 1},
    matchMedia: (query) => ({
      matches:
        (query.includes('display-mode: standalone') && standalone)
        || (query.includes('max-width: 820px') && maxWidth)
        || (query.includes('pointer: coarse') && coarse),
    }),
  };
}

describe('mobile shortcut prompt', () => {
  it('asks only on first mobile browser visit', () => {
    expect(shouldAskShortcutPrompt({
      mobile: true,
      standalone: false,
      choice: '',
    })).toBe(true);
    expect(shouldAskShortcutPrompt({mobile: false, standalone: false, choice: ''})).toBe(false);
    expect(shouldAskShortcutPrompt({mobile: true, standalone: true, choice: ''})).toBe(false);
    expect(shouldAskShortcutPrompt({mobile: true, standalone: false, choice: 'dismissed'})).toBe(false);
  });

  it('detects mobile, iOS and installed display', () => {
    expect(isMobileViewport(fakeWindow({ua: 'iPhone'}))).toBe(true);
    expect(isIosDevice(fakeWindow({ua: 'iPhone'}))).toBe(true);
    expect(isStandaloneDisplay(fakeWindow({standalone: true}))).toBe(true);
    expect(isMobileViewport(fakeWindow({
      ua: 'Mozilla/5.0',
      maxWidth: false,
      coarse: false,
    }))).toBe(false);
  });

  it('remembers the first-visit answer in storage', () => {
    const storage = new Map();
    const adapter = {
      getItem: (key) => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value),
    };
    expect(readShortcutChoice(adapter)).toBe('');
    writeShortcutChoice('dismissed', adapter);
    expect(readShortcutChoice(adapter)).toBe('dismissed');
  });

  it('explains iOS add-to-home-screen when native install is unavailable', () => {
    expect(shortcutInstructionText(true)).toContain('Ana Ekrana Ekle');
    expect(shortcutInstructionText(false)).toContain('Ana ekrana ekle');
  });
});
