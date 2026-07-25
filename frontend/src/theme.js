import {useEffect, useState} from 'react';

// Deneysel UI teması: 'classic' (mevcut/varsayılan tasarım) | 'modern' (yeni tasarım).
// Tercih localStorage'da saklanır; 'modern' seçiliyse <html data-ui-theme="modern">
// üzerinden theme-modern.css devreye girer. Klasik tasarım hiçbir şekilde değişmez.
const THEME_KEY = 'isg_ui_theme';

export function getStoredUiTheme() {
  try {
    return localStorage.getItem(THEME_KEY) === 'modern' ? 'modern' : 'classic';
  } catch (_) {
    return 'classic';
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
