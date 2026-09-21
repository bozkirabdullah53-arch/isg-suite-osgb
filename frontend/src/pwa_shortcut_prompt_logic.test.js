import {describe, expect, it} from 'vitest';

import {
  ACCEPTED_REASK_AFTER_MS,
  DISMISSED_REASK_AFTER_MS,
  isIosDevice,
  isMobileViewport,
  isStandaloneDisplay,
  readShortcutChoice,
  readShortcutEntry,
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

function fakeStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
  };
}

describe('mobile shortcut prompt', () => {
  it('asks before the user has answered and not when already installed', () => {
    const now = Date.now();
    expect(shouldAskShortcutPrompt({
      mobile: true,
      standalone: false,
      choice: '',
      now,
    })).toBe(true);
    expect(shouldAskShortcutPrompt({mobile: false, standalone: false, choice: '', now})).toBe(true);
    expect(shouldAskShortcutPrompt({mobile: true, standalone: true, choice: '', now})).toBe(false);
    expect(shouldAskShortcutPrompt({
      mobile: true,
      standalone: false,
      choice: 'dismissed',
      choiceTime: now,
      now,
    })).toBe(false);
    expect(shouldAskShortcutPrompt({
      mobile: true,
      standalone: false,
      choice: 'installed',
      choiceTime: 0,
      now,
    })).toBe(false);
  });

  it('re-asks after the grace periods expire', () => {
    const now = Date.now();
    expect(shouldAskShortcutPrompt({
      choice: 'dismissed',
      choiceTime: now - DISMISSED_REASK_AFTER_MS - 1000,
      now,
    })).toBe(true);
    expect(shouldAskShortcutPrompt({
      choice: 'dismissed',
      choiceTime: now - DISMISSED_REASK_AFTER_MS + 60_000,
      now,
    })).toBe(false);
    expect(shouldAskShortcutPrompt({
      choice: 'accepted',
      choiceTime: now - ACCEPTED_REASK_AFTER_MS - 1000,
      now,
    })).toBe(true);
    expect(shouldAskShortcutPrompt({
      choice: 'installed',
      choiceTime: now - DISMISSED_REASK_AFTER_MS * 10,
      now,
    })).toBe(false);
  });

  it('asks again for legacy v1 answers without timestamp', () => {
    expect(shouldAskShortcutPrompt({choice: 'dismissed', choiceTime: 0, now: Date.now()})).toBe(true);
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

  it('remembers the answer with a timestamp in storage', () => {
    const storage = fakeStorage();
    expect(readShortcutChoice(storage)).toBe('');
    writeShortcutChoice('dismissed', storage);
    const entry = readShortcutEntry(storage);
    expect(entry.choice).toBe('dismissed');
    expect(entry.time).toBeGreaterThan(Date.now() - 5000);
  });

  it('reads legacy v1 plain-string choices', () => {
    const storage = fakeStorage({isg_pwa_shortcut_choice_v1: 'dismissed'});
    const entry = readShortcutEntry(storage);
    expect(entry.choice).toBe('dismissed');
    expect(entry.time).toBe(0);
    writeShortcutChoice('accepted', storage);
    expect(readShortcutEntry(storage).choice).toBe('accepted');
  });

  it('explains iOS add-to-home-screen when native install is unavailable', () => {
    expect(shortcutInstructionText(true)).toContain('Ana Ekrana Ekle');
    expect(shortcutInstructionText(false, true)).toContain('Ana ekrana ekle');
    expect(shortcutInstructionText(false, false)).toContain('masaüstüne');
  });
});
