import {afterEach, describe, expect, it} from 'vitest';
import {
  beginCsgbPrint,
  endCsgbPrint,
  isCsgbAuditPage,
  isCsgbPrintButton,
  markCsgbPrintElements,
} from './csgb_audit_print_logic';

function renderAuditPage() {
  document.title = 'İSG Suite';
  document.body.innerHTML = `
    <div class="app-shell">
      <aside>Menü</aside>
      <section class="workspace">
        <header>Üst başlık</header>
        <main class="content">
          <div class="page-title">
            <div>
              <h3>ÇSGB Denetim Belge Paketi</h3>
              <p>Checklist + tek tık ZIP</p>
            </div>
            <div><button type="button">Yazdır</button></div>
          </div>

          <section class="panel ibys-panel">
            <h3>İBYS yükleme paketi</h3>
            <button type="button">İBYS CSV paketi indir</button>
          </section>

          <section class="panel selector-panel">
            <label>İşyeri snapshot (müfettiş)<select><option>Tüm OSGB</option></select></label>
          </section>

          <section class="panel summary-panel">
            <h2>Denetim OSGB</h2>
            <div>%45 Hazırlık</div>
          </section>

          <div class="filters">
            <button type="button">Öncelikli (11)</button>
            <button type="button">Tümü (19)</button>
            <button type="button">Hazır (8)</button>
          </div>

          <section class="panel group-panel">
            <h3>Kurumsal ve yetki</h3>
            <div class="table-wrap">
              <table>
                <thead><tr><th></th><th>Durum</th><th>Kalem</th><th>Adet</th><th>Açıklama</th><th>Dayanak</th><th>İşlem</th></tr></thead>
                <tbody><tr><td>+</td><td>Eksik</td><td>Yetki</td><td>0</td><td>Kayıt yok</td><td>Mevzuat</td><td><button>Düzenle</button></td></tr></tbody>
              </table>
            </div>
          </section>
        </main>
      </section>
    </div>`;
}

afterEach(() => {
  endCsgbPrint(document);
  document.body.innerHTML = '';
  document.title = 'İSG Suite';
});

describe('ÇSGB audit print mode', () => {
  it('recognizes only the audit page and its print button', () => {
    renderAuditPage();
    const button = [...document.querySelectorAll('button')].find((node) => node.textContent === 'Yazdır');
    expect(isCsgbAuditPage(document)).toBe(true);
    expect(isCsgbPrintButton(button)).toBe(true);
    expect(isCsgbPrintButton(document.querySelector('.ibys-panel button'))).toBe(false);
  });

  it('marks controls as hidden and tables as printable', () => {
    renderAuditPage();
    expect(markCsgbPrintElements(document)).toBe(true);
    expect(document.querySelector('.page-title').classList.contains('csgb-print-report-title')).toBe(true);
    expect(document.querySelector('.ibys-panel').classList.contains('csgb-print-hidden')).toBe(true);
    expect(document.querySelector('.selector-panel').classList.contains('csgb-print-hidden')).toBe(true);
    expect(document.querySelector('.filters').classList.contains('csgb-print-hidden')).toBe(true);
    expect(document.querySelector('.group-panel').classList.contains('csgb-print-table-panel')).toBe(true);
    expect(document.querySelector('table').classList.contains('csgb-print-table')).toBe(true);
    expect(document.querySelector('.summary-panel').classList.contains('csgb-print-hidden')).toBe(false);
  });

  it('activates and fully cleans isolated print state', () => {
    renderAuditPage();
    expect(beginCsgbPrint(document)).toBe(true);
    expect(document.documentElement.getAttribute('data-csgb-audit-print')).toBe('1');
    expect(document.title).toBe('CSGB-Denetim-Belge-Paketi');

    endCsgbPrint(document);
    expect(document.documentElement.hasAttribute('data-csgb-audit-print')).toBe(false);
    expect(document.documentElement.hasAttribute('data-csgb-audit-original-title')).toBe(false);
    expect(document.title).toBe('İSG Suite');
    expect(document.querySelector('.csgb-print-hidden')).toBe(null);
    expect(document.querySelector('.csgb-print-table')).toBe(null);
  });

  it('does not alter an unrelated page', () => {
    document.body.innerHTML = '<main class="content"><h3>Finans</h3><button>Yazdır</button></main>';
    expect(beginCsgbPrint(document)).toBe(false);
    expect(document.documentElement.hasAttribute('data-csgb-audit-print')).toBe(false);
  });
});
