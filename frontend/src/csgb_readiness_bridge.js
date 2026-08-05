import {api} from './api';
import {buildCsgbReadinessView} from './csgb_readiness_logic';
import './csgb_readiness_bridge.css';

const BRIDGE_CLASS = 'csgb-readiness-advice';
let scanTimer = null;
let requestInFlight = false;

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function integrationPanel() {
  const heading = [...document.querySelectorAll('h3')].find(
    (node) => String(node.textContent || '').trim() === 'Entegrasyon hazırlık',
  );
  return heading?.closest('section') || null;
}

function csgbRow(panel) {
  return [...(panel?.querySelectorAll('li') || [])].find((row) =>
    [...row.querySelectorAll('strong')].some(
      (node) => String(node.textContent || '').trim() === 'ÇSGB denetim paketi',
    ),
  ) || null;
}

function csgbPackButton(panel) {
  return [...(panel?.querySelectorAll('button') || [])].find((button) =>
    String(button.textContent || '').includes('İBYS / ÇSGB paketi'),
  ) || null;
}

function findOsgbSelector(orgs) {
  const ids = new Set(orgs.map((row) => String(row.id)));
  const names = new Set(orgs.map((row) => String(row.name || '').trim()).filter(Boolean));
  return [...document.querySelectorAll('select')].find((select) => {
    const options = [...select.options].filter((option) => option.value !== '');
    if (!options.length) return false;
    const valuesMatch = options.every((option) => ids.has(String(option.value)));
    const nameMatches = options.some((option) => names.has(String(option.textContent || '').trim()));
    return valuesMatch && nameMatches;
  }) || null;
}

async function resolveOsgbId() {
  const orgs = await api('/osgb');
  const list = Array.isArray(orgs) ? orgs : [];
  if (!list.length) return null;
  if (list.length === 1) return Number(list[0].id);

  const selector = findOsgbSelector(list);
  if (selector && !selector.dataset.csgbReadinessListener) {
    selector.dataset.csgbReadinessListener = '1';
    selector.addEventListener('change', () => {
      document.querySelector(`.${BRIDGE_CLASS}`)?.remove();
      window.setTimeout(scheduleScan, 250);
    });
  }
  const selected = Number(selector?.value || 0);
  return selected || Number(list[0].id);
}

function openCsgbPack(panel, priority) {
  try {
    sessionStorage.setItem('csgb_focus_code', priority.code || '');
    sessionStorage.setItem('csgb_focus_module', priority.actionModule || 'csgb_audit');
  } catch {
    // Navigation still works without session storage.
  }
  csgbPackButton(panel)?.click();
}

function renderAdvice(panel, row, view, osgbId) {
  row.querySelector(`.${BRIDGE_CLASS}`)?.remove();
  if (!view.hasDetails) return;

  const bridge = document.createElement('div');
  bridge.className = BRIDGE_CLASS;
  bridge.dataset.osgbId = String(osgbId);
  bridge.dataset.priorityCount = String(view.priorityCount);

  const notesHtml = view.contextualNotes
    .map((note) => `
      <div class="csgb-readiness-advice__context">
        <strong>${escapeHtml(note.title)}</strong><br>
        ${escapeHtml(note.detail)}
        ${note.legalBasis ? `<br><small>${escapeHtml(note.legalBasis)}</small>` : ''}
      </div>`)
    .join('');

  const prioritiesHtml = view.priorities
    .map((priority, index) => {
      const statusClass = priority.contextReview
        ? 'is-context'
        : priority.status === 'partial'
          ? 'is-partial'
          : '';
      const statusText = priority.contextReview
        ? 'İncele'
        : priority.status === 'partial'
          ? 'Kısmi'
          : 'Eksik';
      return `
        <li class="csgb-readiness-advice__item" data-priority-index="${index}">
          <span class="csgb-readiness-advice__status ${statusClass}">${statusText}</span>
          <div class="csgb-readiness-advice__body">
            <strong>${escapeHtml(priority.title)}</strong>
            <span>${escapeHtml(priority.detail)}</span>
            <span><b>Yapılacak:</b> ${escapeHtml(priority.actionLabel)}</span>
          </div>
          <button type="button" class="csgb-readiness-advice__action" data-open-priority="${index}">
            Pakette aç
          </button>
        </li>`;
    })
    .join('');

  bridge.innerHTML = `
    ${notesHtml}
    <details>
      <summary>${view.priorityCount} önceliğin tamamını görüntüle ve düzelt</summary>
      <ul class="csgb-readiness-advice__list">${prioritiesHtml}</ul>
    </details>`;

  bridge.querySelectorAll('[data-open-priority]').forEach((button) => {
    button.addEventListener('click', () => {
      const priority = view.priorities[Number(button.dataset.openPriority)];
      if (priority) openCsgbPack(panel, priority);
    });
  });
  row.appendChild(bridge);
}

async function attachAdvice() {
  const panel = integrationPanel();
  const row = csgbRow(panel);
  if (!panel || !row || requestInFlight) return;

  requestInFlight = true;
  try {
    const osgbId = await resolveOsgbId();
    if (!osgbId) return;
    const payload = await api(`/osgb/integration-readiness?osgb_id=${encodeURIComponent(osgbId)}`);
    const csgbItem = (payload?.checklist || []).find((item) => item.code === 'csgb_pack');
    const view = buildCsgbReadinessView(csgbItem);
    const existing = row.querySelector(`.${BRIDGE_CLASS}`);
    if (
      existing?.dataset.osgbId === String(osgbId)
      && existing?.dataset.priorityCount === String(view.priorityCount)
    ) {
      return;
    }
    if (row.isConnected) renderAdvice(panel, row, view, osgbId);
  } catch {
    // Existing dashboard remains fully functional when advice cannot be loaded.
  } finally {
    requestInFlight = false;
  }
}

function scheduleScan() {
  window.clearTimeout(scanTimer);
  scanTimer = window.setTimeout(() => void attachAdvice(), 120);
}

const observer = new MutationObserver(scheduleScan);
observer.observe(document.documentElement, {childList: true, subtree: true});
scheduleScan();
