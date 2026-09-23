import {readFileSync} from 'node:fs';
import {afterEach, describe, expect, it} from 'vitest';
import {Window} from 'happy-dom';

const css = ['styles.base.css', 'styles.css', 'theme-modern.css', 'workplace_status.css']
  .map((file) => readFileSync(new URL(file, import.meta.url), 'utf8').replace(/^@import[^;]+;/gm, ''))
  .join('\n');
const windows = [];

function documentFor(markup, mediaType = 'print') {
  const window = new Window({settings: {device: {mediaType}}});
  windows.push(window);
  window.document.head.innerHTML = `<style>${css}</style>`;
  window.document.body.innerHTML = `<div id="root">${markup}</div>`;
  return window;
}

function expectPrinted(window, selector) {
  const element = window.document.querySelector(selector);
  expect(element).not.toBeNull();
  expect(window.getComputedStyle(element).visibility).not.toBe('hidden');
  for (let parent = element; parent; parent = parent.parentElement) {
    expect(window.getComputedStyle(parent).display, `${parent.tagName}.${parent.className}`).not.toBe('none');
  }
}

const companyReport = `
  <div class="app-shell">
    <aside>OSGB menüsü</aside>
    <section class="workspace">
      <header>Uygulama başlığı</header>
      <main class="content">
        <div class="page customer-360-page">
          <header class="page-head"><h2>Örnek Firma</h2><div class="customer-360-actions"><button>Yazdır</button></div></header>
          <section class="customer-360-company-picker"><select><option>Örnek Firma</option></select></section>
          <section class="panel"><h3>Genel uyum durumu</h3><p>%64</p></section>
          <section class="panel"><div class="table-wrap"><table><tbody><tr><td>Risk değerlendirmesi</td><td>Tamamlandı</td></tr></tbody></table></div></section>
        </div>
      </main>
    </section>
  </div>`;

afterEach(async () => {
  await Promise.all(windows.splice(0).map((window) => window.happyDOM.close()));
});

describe('print stylesheet isolation', () => {
  it.each(['classic', 'modern'])('prints the company report in the %s theme while hiding navigation and controls', (theme) => {
    const window = documentFor(companyReport);
    window.document.documentElement.dataset.uiTheme = theme;
    expect(window.matchMedia('print').matches).toBe(true);
    for (const selector of ['.customer-360-page h2', '.panel h3', 'td']) expectPrinted(window, selector);
    for (const selector of ['aside', '.workspace > header', '.customer-360-actions', '.customer-360-company-picker']) {
      expect(window.getComputedStyle(window.document.querySelector(selector)).display).toBe('none');
    }
    expect(window.getComputedStyle(window.document.querySelector('.app-shell')).display).toBe('block');
    expect(window.getComputedStyle(window.document.querySelector('.table-wrap')).overflow).toBe('visible');
  });

  it('does not hide other app reports when the training verification page is absent', () => {
    const window = documentFor('<div class="app-shell"><main class="content"><section class="panel"><h2>Hizmet Denetimi</h2></section></main></div>');
    expectPrinted(window, 'h2');
  });

  it('keeps the public training certificate printable and hides unrelated content', () => {
    const window = documentFor(`
      <main class="login-shell training-verify-shell"><section class="training-verify-card">
        <h1>Belge Doğrulama</h1>
        <div class="training-verify-actions"><button>Yazdır</button></div>
        <div class="training-verify-result"><article class="training-verify-print-certificate"><h2>Eğitim Katılım Belgesi</h2></article></div>
      </section></main><div class="unrelated">Diğer içerik</div>`);
    expectPrinted(window, '.training-verify-print-certificate h2');
    for (const selector of ['.unrelated', '.training-verify-actions', '.training-verify-card > h1']) {
      expect(window.getComputedStyle(window.document.querySelector(selector)).display).toBe('none');
    }
  });

  it('preserves the company screen layout and its print action outside print media', () => {
    const window = documentFor(companyReport, 'screen');
    expectPrinted(window, 'aside');
    expectPrinted(window, '.customer-360-actions button');
    expectPrinted(window, '.customer-360-company-picker select');
    expect(window.getComputedStyle(window.document.querySelector('.app-shell')).display).toBe('grid');
  });
});
