export const PWA_SHORTCUT_STORAGE_KEY = 'isg_pwa_shortcut_choice_v2';
export const LEGACY_PWA_SHORTCUT_STORAGE_KEY = 'isg_pwa_shortcut_choice_v1';

export const DISMISSED_REASK_AFTER_MS = 7 * 24 * 60 * 60 * 1000;
export const ACCEPTED_REASK_AFTER_MS = 24 * 60 * 60 * 1000;

export function isStandaloneDisplay(win = typeof window === 'undefined' ? undefined : window) {
  if (!win) return false;
  const nav = win.navigator || {};
  return Boolean(
    win.matchMedia?.('(display-mode: standalone)')?.matches
    || win.matchMedia?.('(display-mode: fullscreen)')?.matches
    || nav.standalone === true,
  );
}

export function isMobileViewport(win = typeof window === 'undefined' ? undefined : window) {
  if (!win) return false;
  const ua = String(win.navigator?.userAgent || '');
  const coarse = Boolean(win.matchMedia?.('(pointer: coarse)')?.matches);
  const narrow = Boolean(win.matchMedia?.('(max-width: 820px)')?.matches);
  return coarse || narrow || /Android|iPhone|iPad|iPod|Mobile/i.test(ua);
}

export function isIosDevice(win = typeof window === 'undefined' ? undefined : window) {
  if (!win) return false;
  const nav = win.navigator || {};
  const ua = String(nav.userAgent || '');
  return /iPhone|iPad|iPod/i.test(ua)
    || (nav.platform === 'MacIntel' && Number(nav.maxTouchPoints || 0) > 1);
}

/**
 * Otomasyon (E2E / headless) oturumu mu?
 *
 * ``navigator.webdriver`` tarayıcı tarafından sürülen oturumlarda true olur.
 * Amaç testleri "atlatmak" değil, ekranı kaplayan bir istemi otomatik
 * oturuma dayatmamaktır; gerçek kullanıcı bu bayrağı görmez.
 */
export function isAutomatedSession(win = typeof window === 'undefined' ? undefined : window) {
  return Boolean(win?.navigator?.webdriver);
}

function parseEntry(raw) {
  const text = String(raw || '').trim();
  if (!text) return {choice: '', time: 0};
  if (text.startsWith('{')) {
    try {
      const parsed = JSON.parse(text);
      return {
        choice: String(parsed?.choice || '').trim(),
        time: Number(parsed?.time) > 0 ? Number(parsed.time) : 0,
      };
    } catch (_) {
      return {choice: '', time: 0};
    }
  }
  return {choice: text, time: 0};
}

export function readShortcutEntry(storage) {
  try {
    const current = parseEntry(storage?.getItem?.(PWA_SHORTCUT_STORAGE_KEY));
    if (current.choice) return current;
    return parseEntry(storage?.getItem?.(LEGACY_PWA_SHORTCUT_STORAGE_KEY));
  } catch (_) {
    return {choice: '', time: 0};
  }
}

export function readShortcutChoice(storage) {
  return readShortcutEntry(storage).choice;
}

export function writeShortcutChoice(value, storage) {
  const next = String(value || '').trim();
  if (!next || !storage?.setItem) return;
  try {
    storage.setItem(
      PWA_SHORTCUT_STORAGE_KEY,
      JSON.stringify({choice: next, time: Date.now()}),
    );
  } catch (_) {
    // Prompt remains usable when browser storage is blocked.
  }
}

export function shouldAskShortcutPrompt({
  standalone = false,
  automated = false,
  choice = '',
  choiceTime = 0,
  now = Date.now(),
} = {}) {
  if (standalone) return false;
  // Otomasyon (E2E/headless) oturumuna modal dayatılmaz: ekranı kaplayan istem
  // sayfa etkileşimlerini keser. Gerçek kullanıcı davranışı değişmez.
  if (automated) return false;
  const answer = String(choice || '').trim();
  if (!answer) return true;
  if (!['dismissed', 'accepted', 'installed'].includes(answer)) return true;
  if (answer === 'installed') return false;
  if (answer === 'dismissed') return now - Number(choiceTime || 0) >= DISMISSED_REASK_AFTER_MS;
  return now - Number(choiceTime || 0) >= ACCEPTED_REASK_AFTER_MS;
}

export function shortcutInstructionText(ios, mobile = true) {
  if (ios) {
    return 'Safari paylaş menüsünden Ana Ekrana Ekle’yi seçin. Kısayol telefonunuzun ana ekranına yerleşir.';
  }
  if (mobile) {
    return 'Tarayıcı menüsünden Ana ekrana ekle / Uygulamayı yükle’yi seçin. Kısayol telefonunuzun ana ekranına yerleşir.';
  }
  return 'Chrome veya Edge menüsünden Uygulamayı yükle / Bu siteyi uygulama olarak yükle seçeneğini kullanın. İSG Suite masaüstüne eklenir.';
}
