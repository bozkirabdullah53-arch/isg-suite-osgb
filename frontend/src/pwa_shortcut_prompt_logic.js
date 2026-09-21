export const PWA_SHORTCUT_STORAGE_KEY = 'isg_pwa_shortcut_choice_v1';

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

export function readShortcutChoice(storage) {
  try {
    return String(storage?.getItem?.(PWA_SHORTCUT_STORAGE_KEY) || '').trim();
  } catch (_) {
    return '';
  }
}

export function writeShortcutChoice(value, storage) {
  const next = String(value || '').trim();
  if (!next || !storage?.setItem) return;
  try {
    storage.setItem(PWA_SHORTCUT_STORAGE_KEY, next);
  } catch (_) {
    // Prompt remains usable when browser storage is blocked.
  }
}

export function shouldAskShortcutPrompt({standalone = false, mobile = false, choice = ''} = {}) {
  if (standalone) return false;
  return !['dismissed', 'accepted', 'installed'].includes(String(choice || '').trim());
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
