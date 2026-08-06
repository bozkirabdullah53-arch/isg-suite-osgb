import {api, downloadFile} from './api';
import {
  buildPerformanceExcelDownload,
  replaceCsvLabel,
  reportStamp,
} from './professional_performance_excel_logic';

const QUICK_LINK_TITLES = new Map([
  ['ÇSGB belge paketi', 'Denetim checklist, kanıt dosyaları ve ZIP indirme ekranını açar.'],
  ['Hizmet denetimi', 'Profesyonellerin işyeri ve mevzuat kontrollerini açar.'],
  ['Performans raporu', 'Uzman, hekim ve DSP bazında ayrıntılı performans ekranını açar.'],
  ['Finans', 'Tahakkuk ve ödeme kayıtlarını açar.'],
]);

let scanTimer = null;
let downloadBusy = false;

function normalizedText(node) {
  return String(node?.textContent || '').replace(/\s+/g, ' ').trim();
}

function replaceTextNodes(node) {
  if (!node) return;
  if (node.nodeType === Node.TEXT_NODE) {
    node.nodeValue = replaceCsvLabel(node.nodeValue);
    return;
  }
  for (const child of node.childNodes || []) replaceTextNodes(child);
}

function decorateExportButtons() {
  for (const button of document.querySelectorAll('button')) {
    const text = normalizedText(button);
    if (text === 'Profesyonel performans CSV') {
      button.dataset.performanceExcelKind = 'roster';
      button.title = 'Türkçe başlıklı, filtreli ve çok sayfalı profesyonel performans Excel raporunu indirir.';
      replaceTextNodes(button);
    } else if (text === 'OSGB CSV') {
      button.dataset.performanceExcelKind = 'roster';
      button.title = 'OSGB genelindeki profesyonellerin biçimlendirilmiş Excel raporunu indirir.';
      replaceTextNodes(button);
    } else if (text === 'Detay CSV') {
      button.dataset.performanceExcelKind = 'detail';
      button.title = 'Seçili profesyonelin özet, eksik, tamamlanan ve firma checklist Excel raporunu indirir.';
      replaceTextNodes(button);
    }
  }
}

function decorateQuickLinks() {
  const heading = [...document.querySelectorAll('h3')].find(
    (node) => normalizedText(node) === 'Dışa aktarım & hızlı geçiş',
  );
  const panel = heading?.closest('section');
  if (!panel) return;

  for (const button of panel.querySelectorAll('button')) {
    const title = QUICK_LINK_TITLES.get(normalizedText(button));
    if (title) button.title = title;
  }

  if (!panel.querySelector('[data-performance-excel-note]')) {
    const note = document.createElement('p');
    note.dataset.performanceExcelNote = '1';
    note.style.margin = '10px 0 0';
    note.style.fontSize = '12px';
    note.style.color = '#64748b';
    note.textContent = 'Excel düğmesi, sütunları düzenlenmiş çok sayfalı rapor indirir. Diğer düğmeler ilgili yönetim ekranına geçer.';
    panel.appendChild(note);
  }
}

function selectedProfessionalId() {
  const heading = [...document.querySelectorAll('h3')].find((node) =>
    normalizedText(node).startsWith('Profesyonel:'),
  );
  const name = normalizedText(heading).replace(/^Profesyonel:\s*/i, '').trim();
  const selects = [...document.querySelectorAll('select')];

  if (name) {
    const matching = selects.find((select) => {
      const option = select.options?.[select.selectedIndex];
      return Number(select.value || 0) > 0 && normalizedText(option).includes(name);
    });
    if (matching) return Number(matching.value);
  }

  const likely = selects.find((select) => {
    if (Number(select.value || 0) <= 0) return false;
    const labels = [...(select.options || [])].map((option) => normalizedText(option));
    return labels.some((label) => /Sınıf\s+[ABC]/i.test(label) || /\(pasif\)/i.test(label));
  });
  return Number(likely?.value || 0);
}

async function currentOsgbId() {
  const orgs = await api('/osgb');
  const list = Array.isArray(orgs) ? orgs : [];
  if (!list.length) throw new Error('OSGB kaydı bulunamadı.');
  if (list.length === 1) return Number(list[0].id);

  const ids = new Set(list.map((org) => String(org.id)));
  const selector = [...document.querySelectorAll('select')].find((select) => {
    const options = [...(select.options || [])].filter((option) => option.value !== '');
    return options.length > 0 && options.every((option) => ids.has(String(option.value)));
  });
  return Number(selector?.value || list[0].id);
}

async function handleExcelDownload(button, kind) {
  if (downloadBusy) return;
  downloadBusy = true;
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  try {
    const osgbId = kind === 'detail' ? undefined : await currentOsgbId();
    const professionalId = kind === 'detail' ? selectedProfessionalId() : undefined;
    const target = buildPerformanceExcelDownload(kind, {
      osgbId,
      professionalId,
      stamp: reportStamp(),
    });
    await downloadFile(target.path, target.filename);
  } catch (error) {
    window.alert(error?.message || 'Excel raporu indirilemedi.');
  } finally {
    button.disabled = false;
    button.removeAttribute('aria-busy');
    downloadBusy = false;
  }
}

function onDocumentClick(event) {
  const button = event.target?.closest?.('button[data-performance-excel-kind]');
  if (!button) return;
  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();
  void handleExcelDownload(button, button.dataset.performanceExcelKind);
}

function scan() {
  decorateExportButtons();
  decorateQuickLinks();
}

function scheduleScan() {
  window.clearTimeout(scanTimer);
  scanTimer = window.setTimeout(scan, 80);
}

document.addEventListener('click', onDocumentClick, true);
const observer = new MutationObserver(scheduleScan);
observer.observe(document.documentElement, {childList: true, subtree: true});
scheduleScan();
