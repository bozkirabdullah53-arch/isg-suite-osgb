import {api} from './api';
import {
  normalizePresentationReadiness,
  parseSavedTrainingId,
  shouldRenderPresentationPanel,
} from './training_presentation_readiness_logic';
import './training_presentation_readiness.css';

const PANEL_CLASS = 'training-presentation-panel';
const cache = new Map();
const inFlight = new Set();
let timer = null;

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function outputPanel() {
  return document.querySelector('section.education-output-panel');
}

function removePanelsExcept(trainingId) {
  document.querySelectorAll(`.${PANEL_CLASS}`).forEach((panel) => {
    if (String(panel.dataset.trainingId || '') !== String(trainingId || '')) panel.remove();
  });
}

function renderPanel(anchor, view) {
  removePanelsExcept(view.trainingId);
  const existing = document.querySelector(`.${PANEL_CLASS}[data-training-id="${view.trainingId}"]`);
  if (existing) return;

  const section = document.createElement('section');
  section.className = `panel ${PANEL_CLASS}`;
  section.dataset.trainingId = String(view.trainingId);
  section.setAttribute('aria-labelledby', `trainingPresentationTitle-${view.trainingId}`);

  const naceText = view.classification.naceCode
    ? `${view.classification.naceCode} · ${view.classification.naceDescription || 'NACE açıklaması'}`
    : 'Doğrulanmış NACE bilgisi bekleniyor';
  const checkItems = view.checks.map((check) => `
    <li class="training-presentation-panel__check">
      <span class="status-badge ${check.ok ? 'badge-ok' : 'badge-warn'}">
        ${check.ok ? 'Hazır' : 'Bekliyor'}
      </span>
      <div>
        <strong>${escapeHtml(check.label)}</strong>
        <span>${escapeHtml(check.detail)}</span>
      </div>
    </li>`).join('');

  section.innerHTML = `
    <div class="training-presentation-panel__header">
      <div>
        <h3 id="trainingPresentationTitle-${view.trainingId}">NACE Uyumlu Eğitim Sunumu</h3>
        <p>
          Salt okunur hazırlık denetimi · ${escapeHtml(naceText)}
          ${view.classification.hazardClass ? ` · ${escapeHtml(view.classification.hazardClass)}` : ''}
        </p>
      </div>
      <span class="status-badge badge-warn">Planlama aşaması</span>
    </div>
    <ul class="training-presentation-panel__checks">${checkItems}</ul>
    <p class="training-presentation-panel__next">
      <strong>Sonraki adım:</strong> ${escapeHtml(view.nextAction)}
      Eğitim, sınav, PDF ve sertifika işlemleri bu hazırlık panelinden bağımsızdır.
    </p>`;
  anchor.insertAdjacentElement('afterend', section);
}

function applyPayload(anchor, raw) {
  const view = normalizePresentationReadiness(raw);
  if (!shouldRenderPresentationPanel(view)) {
    removePanelsExcept(null);
    return;
  }
  renderPanel(anchor, view);
}

async function attach() {
  const anchor = outputPanel();
  if (!anchor) {
    removePanelsExcept(null);
    return;
  }
  const trainingId = parseSavedTrainingId(anchor.textContent);
  if (!trainingId) {
    removePanelsExcept(null);
    return;
  }
  removePanelsExcept(trainingId);
  const existing = document.querySelector(`.${PANEL_CLASS}[data-training-id="${trainingId}"]`);
  if (existing) return;
  if (cache.has(trainingId)) {
    applyPayload(anchor, cache.get(trainingId));
    return;
  }
  if (inFlight.has(trainingId)) return;

  inFlight.add(trainingId);
  try {
    const payload = await api(`/trainings/${trainingId}/presentation-readiness`);
    cache.set(trainingId, payload);
    if (anchor.isConnected) applyPayload(anchor, payload);
  } catch {
    // Optional feature: an unavailable readiness endpoint must not affect the
    // existing training, exam, PDF or certificate controls.
    removePanelsExcept(null);
  } finally {
    inFlight.delete(trainingId);
  }
}

function scheduleAttach() {
  window.clearTimeout(timer);
  timer = window.setTimeout(() => void attach(), 120);
}

new MutationObserver(scheduleAttach).observe(document.documentElement, {
  childList: true,
  subtree: true,
  characterData: true,
});
window.addEventListener('hashchange', scheduleAttach);
scheduleAttach();
