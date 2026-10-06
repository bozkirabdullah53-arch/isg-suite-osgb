import {expect, test} from 'vitest';
import {Window} from 'happy-dom';
import {readFileSync} from 'node:fs';
const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
const [base, styles, modern, mobile, assistant] = ['styles.base.css', 'styles.css', 'theme-modern.css', 'mobile_layout.css', 'contextual_assistant.css'].map(read);

test.each([320, 360, 390, 430, 620, 621, 768, 1200])('responsive cascade at %ipx preserves usable controls and layout', async (width) => {
  const win = new Window({width, height: 844});
  win.document.write(`<html data-ui-theme="modern"><head><style>${base}${styles.replace('@import "./styles.base.css";', '')}${modern}${mobile}${assistant}</style></head><body>
    <div class="app-shell"><section class="workspace"><header><div class="header-actions"><div class="header-tools"><button class="header-icon">Geri</button><div class="mobile-assistant-slot"><button class="contextual-assistant-launcher">Asistan</button></div></div></div></header>
    <main class="content"><section class="panel employees-page"><div class="form-grid employees-filters"><label class="field"><select><option>Şube</option></select></label></div><div class="employees-table table-wrap"><table></table></div><div class="employees-cards"></div><button class="danger" disabled>Sil</button></section></main></section></div>
    <div class="annual-month-grid"></div><div class="risk-departments-layout"></div><div class="ppe-signature-grid"></div>
    <div class="modal-bg"><section class="modal"><header><h3>Yeni Personel</h3><button class="icon">Kapat</button></header></section></div>
    <a class="global-contact-help">Yardım</a></body></html>`);
  const style = (selector) => win.getComputedStyle(win.document.querySelector(selector));
  expect(style('.danger').backgroundColor).toBe('#b91c1c');
  expect(Number(style('.danger').opacity)).toBe(.5);
  expect(style('.modal > header').margin).toBe('0px');
  expect(style('.modal > header .icon').width).toBe('44px');
  expect(style('.global-contact-help').visibility).toBe('hidden');
  if (width <= 760) {
    expect(style('.employees-filters').gridTemplateColumns).toBe('minmax(0, 1fr)');
    expect(style('.employees-table').display).toBe('none');
    expect(style('.employees-cards').display).toBe('grid');
    expect(style('.ppe-signature-grid').gridTemplateColumns).toBe('minmax(0, 1fr)');
  } else {
    expect(style('.employees-cards').display).toBe('none');
    expect(style('.employees-filters').gridTemplateColumns).toContain('1.4fr');
  }
  if (width <= 620) {
    expect(style('.workspace .header-icon').width).toBe('44px');
    expect(style('.workspace .header-icon').height).toBe('44px');
    expect(style('.mobile-assistant-slot > button').position).toBe('relative');
    expect(style('.annual-month-grid').gridTemplateColumns).toBe('repeat(2, minmax(0, 1fr))');
  }
  if (width <= 980) expect(style('.risk-departments-layout').gridTemplateColumns).toBe('minmax(0, 1fr)');
  await win.happyDOM.close();
});
