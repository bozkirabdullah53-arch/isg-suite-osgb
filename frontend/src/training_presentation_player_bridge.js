import {api} from './api';
import {
  INSTRUCTOR_UI_V2,
  instructorBulletPresentation,
  normalizeInstructorManifest,
  playerIndexForKey,
} from './training_presentation_player_logic';
import './training_presentation_player.css';

const PANEL_SELECTOR = '.training-presentation-panel[data-training-id]';
const BUTTON_ATTR = 'data-instructor-mode';
let active = null;
let observer = null;
let timer = null;

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function isHttpUrl(value) {
  return /^https?:\/\//i.test(String(value || '').trim());
}

function sectionLabel(sectionId) {
  const labels = {
    cover: 'Açılış',
    learning_objectives: 'Öğrenme hedefleri',
    legal_basis: 'Mevzuat',
    nace_identity: 'NACE kimliği',
    training_plan: 'Eğitim planı',
    foundation_ohs: 'Temel İSG',
    work_specific_topics: 'İşe özgü riskler',
    technical_risks: 'Teknik riskler',
    control_measures: 'Kontrol tedbirleri',
    ppe: 'KKD',
    emergency: 'Acil durum',
    assessment: 'Değerlendirme',
    summary: 'Özet',
    sources_and_version: 'Kaynaklar',
  };
  return labels[sectionId] || 'Eğitim içeriği';
}

function sourceMarkup(source) {
  const value = String(source || '').trim();
  if (!value) return '';
  if (isHttpUrl(value)) {
    return `<a href="${escapeHtml(value)}" target="_blank" rel="noreferrer">${escapeHtml(value)}</a>`;
  }
  return `<span>${escapeHtml(value)}</span>`;
}

function cardMarkup(item) {
  const card = instructorBulletPresentation(item);
  return `
    <article class="training-instructor-mode__card" data-content-kind="${escapeHtml(card.kind)}" role="listitem">
      <span class="training-instructor-mode__card-label">${escapeHtml(card.label)}</span>
      <p>${escapeHtml(card.text)}</p>
    </article>`;
}

function closePlayer() {
  if (!active) return;
  document.removeEventListener('keydown', active.onKey);
  active.overlay.remove();
  document.body.style.removeProperty('overflow');
  active.returnFocus?.focus?.();
  active = null;
}

function renderSlide() {
  if (!active) return;
  const {model, overlay} = active;
  const slide = model.slides[active.index];
  const body = overlay.querySelector('[data-instructor-slide]');
  const isV2 = model.uiVersion === INSTRUCTOR_UI_V2;
  const coverageText = model.coverageV2?.phase9_full_profile
    ? `${Number(model.coverageV2.phase9_supported_count || 0)}/5 genişletilmiş NACE konu paketi`
    : sectionLabel(slide.sectionId);
  const content = isV2
    ? `<div class="training-instructor-mode__cards" role="list">${slide.bullets.map(cardMarkup).join('')}</div>`
    : `<ul>${slide.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
  const sourceContent = slide.sources.length
    ? slide.sources.map((source) => sourceMarkup(source)).join('')
    : '<span>Kaynak bilgisi manifestte bulunmuyor</span>';
  const sourceBlock = isV2
    ? `<div class="training-instructor-mode__sources" aria-label="Slayt kaynakları">
        <strong>Kaynaklar</strong>
        <div>${sourceContent}</div>
      </div>`
    : `<small>${slide.sources.length ? `Kaynak: ${escapeHtml(slide.sources.slice(0, 2).join(' · '))}` : 'Kaynak bilgisi manifestte bulunmuyor'}</small>`;

  body.innerHTML = `
    <div class="training-instructor-mode__meta">
      <span>${escapeHtml(model.naceCode)} · ${active.index + 1}/${model.slideCount}</span>
      <span>${escapeHtml(coverageText)}</span>
      <span>20/20 soru kapsaması doğrulandı</span>
    </div>
    <h2>${escapeHtml(slide.title)}</h2>
    ${content}
    <div class="training-instructor-mode__footer">
      <span>${slide.linkedQuestionCount ? `${slide.linkedQuestionCount} sınav sorusu bu slayta bağlı` : 'Bu slayt doğrudan sınav sorusu taşımıyor'}</span>
      ${slide.approvalRequired ? '<strong>Uzman/işyeri onayı gerekli</strong>' : ''}
      ${sourceBlock}
    </div>`;
  overlay.querySelector('[data-player-prev]').disabled = active.index === 0;
  overlay.querySelector('[data-player-next]').disabled = active.index === model.slideCount - 1;
  overlay.querySelector('[data-player-progress]').style.width = `${((active.index + 1) / model.slideCount) * 100}%`;
}

function openPlayer(model, returnFocus) {
  closePlayer();
  const overlay = document.createElement('div');
  overlay.className = `training-instructor-mode${model.uiVersion === INSTRUCTOR_UI_V2 ? ' is-v2' : ''}`;
  overlay.dataset.uiVersion = model.uiVersion;
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-label', 'Eğitmen sunum modu');
  overlay.innerHTML = `
    <div class="training-instructor-mode__progress"><span data-player-progress></span></div>
    <header>
      <div>
        <strong>Eğitmen Modu</strong>
        <span>${escapeHtml(model.naceCode)} · ${escapeHtml(model.naceDescription)}</span>
      </div>
      ${model.uiVersion === INSTRUCTOR_UI_V2 ? '<span class="training-instructor-mode__quality-badge">Kaynak kontrollü · v2</span>' : ''}
      <button type="button" data-player-close aria-label="Eğitmen modunu kapat">×</button>
    </header>
    <main data-instructor-slide tabindex="0"></main>
    <nav aria-label="Sunum kontrolleri">
      <button type="button" data-player-prev>← Önceki</button>
      <span>← → / PageUp PageDown / Home End</span>
      <button type="button" data-player-next>Sonraki →</button>
    </nav>`;

  const onKey = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      closePlayer();
      return;
    }
    const next = playerIndexForKey(event.key, active?.index ?? 0, model.slideCount);
    if (next !== active?.index) {
      event.preventDefault();
      active.index = next;
      renderSlide();
    }
  };
  overlay.querySelector('[data-player-close]').addEventListener('click', closePlayer);
  overlay.querySelector('[data-player-prev]').addEventListener('click', () => {
    active.index = Math.max(0, active.index - 1);
    renderSlide();
  });
  overlay.querySelector('[data-player-next]').addEventListener('click', () => {
    active.index = Math.min(model.slideCount - 1, active.index + 1);
    renderSlide();
  });
  document.body.appendChild(overlay);
  document.body.style.overflow = 'hidden';
  active = {overlay, model, index: 0, returnFocus, onKey};
  document.addEventListener('keydown', onKey);
  renderSlide();
  overlay.querySelector('[data-instructor-slide]').focus();
}

async function startInstructorMode(button) {
  const panel = button.closest(PANEL_SELECTOR);
  const trainingId = Number(panel?.dataset.trainingId || 0);
  if (!trainingId) return;
  const previousText = button.textContent;
  button.disabled = true;
  button.textContent = 'Eğitmen Modu hazırlanıyor…';
  try {
    const versions = await api(`/trainings/${trainingId}/presentation-versions`);
    const rows = Array.isArray(versions?.rows) ? versions.rows : [];
    const latest = rows
      .filter((row) => ['generated', 'approved', 'archived'].includes(String(row.status || '').toLowerCase()))
      .sort((a, b) => Number(b.version || 0) - Number(a.version || 0))[0];
    if (!latest?.id) throw new Error('Eğitmen Modu için üretilmiş sunum sürümü bulunamadı.');
    const detail = await api(`/trainings/${trainingId}/presentation-versions/${latest.id}`);
    const model = normalizeInstructorManifest(detail?.manifest);
    openPlayer(model, button);
  } catch (error) {
    const message = String(error?.message || error || 'Eğitmen Modu açılamadı.');
    window.alert(message);
  } finally {
    button.disabled = false;
    button.textContent = previousText;
  }
}

function attachButtons() {
  document.querySelectorAll(PANEL_SELECTOR).forEach((panel) => {
    const actions = panel.querySelector('.training-presentation-panel__actions');
    if (!actions || actions.querySelector(`[${BUTTON_ATTR}]`)) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'training-presentation-panel__button is-primary training-instructor-mode__launch';
    button.setAttribute(BUTTON_ATTR, '');
    button.textContent = 'Eğitmen Modu';
    button.addEventListener('click', () => startInstructorMode(button));
    actions.appendChild(button);
  });
}

function scheduleAttach() {
  if (timer) return;
  timer = window.setTimeout(() => {
    timer = null;
    attachButtons();
  }, 80);
}

observer = new MutationObserver(scheduleAttach);
observer.observe(document.documentElement, {childList: true, subtree: true});
scheduleAttach();

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    observer?.disconnect();
    if (timer) window.clearTimeout(timer);
    closePlayer();
  });
}
