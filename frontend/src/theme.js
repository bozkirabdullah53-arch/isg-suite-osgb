import {useEffect, useState} from 'react';

// UI teması: 'classic' | 'modern' (premium — varsayılan).
// Tercih localStorage'da saklanır; modern seçiliyse <html data-ui-theme="modern">
// üzerinden theme-modern.css devreye girer. Klasik styles.css dokunulmaz.
const THEME_KEY = 'isg_ui_theme';

export function getStoredUiTheme() {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'classic') return 'classic';
    // modern veya boş/yeni kullanıcı → premium varsayılan
    return 'modern';
  } catch (_) {
    return 'modern';
  }
}

function applyUiTheme(theme) {
  if (theme === 'modern') document.documentElement.dataset.uiTheme = 'modern';
  else delete document.documentElement.dataset.uiTheme;
}

// İlk boyamada (login dahil) tema flaşı olmasın diye import anında uygula.
applyUiTheme(getStoredUiTheme());

export function useUiTheme() {
  const [theme, setTheme] = useState(getStoredUiTheme);
  useEffect(() => {
    applyUiTheme(theme);
    try { localStorage.setItem(THEME_KEY, theme); } catch (_) { /* ignore */ }
  }, [theme]);
  const toggle = () => setTheme((t) => (t === 'modern' ? 'classic' : 'modern'));
  return [theme, toggle];
}
