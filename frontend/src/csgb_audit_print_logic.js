const PRINT_ATTR = 'data-csgb-audit-print';
const ORIGINAL_TITLE_ATTR = 'data-csgb-audit-original-title';

export function isCsgbAuditPage(doc = document) {
  return [...doc.querySelectorAll('h1, h2, h3')].some(
    (node) => String(node.textContent || '').trim() === 'ÇSGB Denetim Belge Paketi',
  );
}

export function markCsgbPrintElements(doc = document) {
  const title = [...doc.querySelectorAll('h1, h2, h3')].find(
    (node) => String(node.textContent || '').trim() === 'ÇSGB Denetim Belge Paketi',
  );
  const content = title?.closest('.content') || doc.querySelector('.content');
  if (!title || !content) return false;

  title.closest('.page-title')?.classList.add('csgb-print-report-title');

  for (const panel of content.querySelectorAll('section.panel')) {
    const hasTable = Boolean(panel.querySelector('table'));
    const hasControl = Boolean(panel.querySelector('select, form'));
    const headingText = [...panel.querySelectorAll('h2, h3')]
      .map((node) => String(node.textContent || '').trim())
      .join(' ');
    if (
      hasControl
      || headingText.includes('İBYS yükleme paketi')
      || headingText.includes('Paket yüklenemedi')
    ) {
      panel.classList.add('csgb-print-hidden');
    }
    if (hasTable) {
      panel.classList.add('csgb-print-table-panel');
      panel.querySelector('.table-wrap')?.classList.add('csgb-print-table-wrap');
      panel.querySelector('table')?.classList.add('csgb-print-table');
    }
  }

  for (const button of content.querySelectorAll('button')) {
    const text = String(button.textContent || '').trim();
    if (
      text.startsWith('Öncelikli (')
      || text.startsWith('Tümü (')
      || text.startsWith('Hazır (')
    ) {
      button.parentElement?.classList.add('csgb-print-hidden');
    }
  }

  return true;
}

export function beginCsgbPrint(doc = document) {
  if (!isCsgbAuditPage(doc)) return false;
  markCsgbPrintElements(doc);
  const root = doc.documentElement;
  root.setAttribute(PRINT_ATTR, '1');
  if (!root.hasAttribute(ORIGINAL_TITLE_ATTR)) {
    root.setAttribute(ORIGINAL_TITLE_ATTR, doc.title || 'İSG Suite');
  }
  doc.title = 'CSGB-Denetim-Belge-Paketi';
  return true;
}

export function endCsgbPrint(doc = document) {
  const root = doc.documentElement;
  root.removeAttribute(PRINT_ATTR);
  const originalTitle = root.getAttribute(ORIGINAL_TITLE_ATTR);
  if (originalTitle !== null) {
    doc.title = originalTitle;
    root.removeAttribute(ORIGINAL_TITLE_ATTR);
  }
  for (const node of doc.querySelectorAll(
    '.csgb-print-report-title, .csgb-print-hidden, .csgb-print-table-panel, .csgb-print-table-wrap, .csgb-print-table',
  )) {
    node.classList.remove(
      'csgb-print-report-title',
      'csgb-print-hidden',
      'csgb-print-table-panel',
      'csgb-print-table-wrap',
      'csgb-print-table',
    );
  }
}

export function isCsgbPrintButton(target) {
  const button = target?.closest?.('button');
  if (!button) return false;
  const text = String(button.textContent || '').trim();
  return text === 'Yazdır' && isCsgbAuditPage(button.ownerDocument);
}
