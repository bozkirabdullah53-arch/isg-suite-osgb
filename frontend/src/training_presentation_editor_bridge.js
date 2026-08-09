import {api} from './api';
import {
  buildPresentationEditPayload,
  canEditPresentationRole,
  editorSlides,
  pickEditableVersion,
} from './training_presentation_editor_logic';
import './training_presentation_editor.css';

const PANEL_SELECTOR = '.training-presentation-panel[data-training-id]';
const BUTTON_ATTR = 'data-presentation-editor-v3';
let observer = null;
let timer = null;
let activeOverlay = null;
let currentUserPromise = null;

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

async function currentUser() {
  if (!currentUserPromise) currentUserPromise = api('/auth/me').catch(() => null);
  return currentUserPromise;
}

function closeEditor() {
  if (!activeOverlay) return;
  activeOverlay.remove();
  activeOverlay = null;
  document.body.style.removeProperty('overflow');
}

async function ensureSourceVersion(trainingId) {
  let history = await api(`/trainings/${trainingId}/presentation-versions`);
  let source = pickEditableVersion(history?.rows);
  if (!source) {
    source = await api(`/trainings/${trainingId}/presentation-versions`, {method: 'POST'});
    history = await api(`/trainings/${trainingId}/presentation-versions`);
    source = pickEditableVersion(history?.rows) || source;
  }
  if (!source?.id) throw new Error('Düzenlenecek sunum sürümü oluşturulamadı.');
  const detail = await api(`/trainings/${trainingId}/presentation-versions/${source.id}`);
  return {source, detail};
}

function field(label, control, wide = false) {
  return `<label class="training-presentation-editor__field${wide ? ' is-wide' : ''}"><span>${escapeHtml(label)}</span>${control}</label>`;
}

function formMarkup(slides, selectedPosition) {
  const selected = slides.find((slide) => slide.position === selectedPosition) || slides[0];
  return `
    <div class="training-presentation-editor__mode">
      <button type="button" class="is-active" data-editor-kind="existing">Mevcut slaytı geliştir</button>
      <button type="button" data-editor-kind="new">Yeni slayt ekle</button>
    </div>
    <h4 data-editor-form-title>${selected ? `${selected.position}. slayt — geliştirme` : 'Sunum geliştirme'}</h4>
    <div class="training-presentation-editor__grid">
      ${field('Slayt başlığı', `<input data-editor-title maxlength="220" value="${escapeHtml(selected?.title || '')}">`, true)}
      ${field('Düzenleme biçimi', `<select data-editor-edit-mode><option value="append">Mevcut içeriği koru + ekle</option><option value="replace">Görünen içeriği eğitmen metniyle değiştir</option></select>`)}
      ${field('V3 zenginleştirme', `<select data-editor-auto><option value="yes">Açık — görsel ders yapısı ekle</option><option value="no">Kapalı — yalnız benim eklediklerim</option></select>`)}
      ${field('Ders anlatım maddeleri (satır başına bir madde)', '<textarea data-editor-points rows="6" placeholder="Örn. Tehlikeyi çalışmaya başlamadan önce tanımla\nKontrol tedbirinin devrede olduğunu doğrula"></textarea>', true)}
      ${field('Vaka / sınıf tartışması', '<textarea data-editor-scenario rows="4" placeholder="Sahadan bir olay veya karar senaryosu yazın."></textarea>', true)}
      ${field('Ana mesaj', '<textarea data-editor-takeaway rows="3" placeholder="Katılımcının slayttan mutlaka hatırlaması gereken cümle."></textarea>', true)}
      ${field('Eğitmen notu (PPTX konuşmacı notuna gider)', '<textarea data-editor-note rows="4" placeholder="Bu slaytı anlatırken verilecek örnek, vurgu veya uygulama notu."></textarea>', true)}
      ${field('Değişiklik notu', '<input data-editor-change-note maxlength="800" placeholder="Örn. saha örneği ve kontrol adımları eklendi">', true)}
    </div>
    <p class="training-presentation-editor__tip" data-editor-tip>
      “Mevcut içeriği koru + ekle” önerilir. Eski sunum sürümü hiçbir durumda değişmez; kaydetme işlemi yeni bir vN taslak oluşturur.
    </p>
    <p class="training-presentation-editor__visual-note">
      Ders Sunumu V3; tehlike → kontrol → güvenli davranış akışı, risk kartları, kontrol hiyerarşisi, acil durum akışı, vaka kutusu ve kaynak altlığı gibi vektör görseller üretir.
    </p>`;
}

function resetFields(overlay, slide, {newSlide = false} = {}) {
  const title = overlay.querySelector('[data-editor-title]');
  const mode = overlay.querySelector('[data-editor-edit-mode]');
  if (title) title.value = newSlide ? '' : (slide?.title || '');
  if (mode) mode.disabled = newSlide;
  for (const selector of ['[data-editor-points]', '[data-editor-scenario]', '[data-editor-takeaway]', '[data-editor-note]', '[data-editor-change-note]']) {
    const node = overlay.querySelector(selector); if (node) node.value = '';
  }
}

function readForm(overlay, state) {
  return {
    position: state.selectedPosition,
    title: overlay.querySelector('[data-editor-title]')?.value || '',
    mode: overlay.querySelector('[data-editor-edit-mode]')?.value || 'append',
    lessonPoints: overlay.querySelector('[data-editor-points]')?.value || '',
    scenario: overlay.querySelector('[data-editor-scenario]')?.value || '',
    keyTakeaway: overlay.querySelector('[data-editor-takeaway]')?.value || '',
    instructorNote: overlay.querySelector('[data-editor-note]')?.value || '',
    changeNote: overlay.querySelector('[data-editor-change-note]')?.value || '',
    autoEnrich: overlay.querySelector('[data-editor-auto]')?.value !== 'no',
  };
}

function setBusy(overlay, busy, message = '', error = false) {
  overlay.querySelectorAll('button, input, select, textarea').forEach((node) => {
    if (!node.matches('[data-editor-close]')) node.disabled = Boolean(busy);
  });
  const status = overlay.querySelector('[data-editor-status]');
  if (status) {
    status.textContent = message;
    status.classList.toggle('is-error', Boolean(error));
  }
}

async function saveEditor(overlay, state, {render = false} = {}) {
  let payload;
  try {
    payload = buildPresentationEditPayload(readForm(overlay, state), {newSlide: state.kind === 'new'});
  } catch (error) {
    setBusy(overlay, false, error.message || String(error), true); return;
  }
  setBusy(overlay, true, render ? 'Yeni V3 sürümü oluşturuluyor ve görsel sunum üretiliyor…' : 'Yeni taslak sürüm oluşturuluyor…');
  try {
    const created = await api(
      `/trainings/${state.trainingId}/presentation-versions/${state.sourceId}/edit-copy`,
      {method: 'POST', body: JSON.stringify(payload)},
    );
    if (render) {
      await api(`/trainings/${state.trainingId}/presentation-versions/${created.id}/render-teaching-v3`, {method: 'POST'});
    }
    const message = render
      ? `Ders Sunumu V3 v${created.version} üretildi. Eski sürümler aynen korundu.`
      : `Yeni v${created.version} taslağı kaydedildi. Eski sürümler aynen korundu.`;
    setBusy(overlay, false, message, false);
    window.setTimeout(() => { closeEditor(); window.location.reload(); }, 700);
  } catch (error) {
    setBusy(overlay, false, String(error?.message || error || 'Sunum düzenleme başarısız.'), true);
  }
}

async function openEditor(button) {
  const panel = button.closest(PANEL_SELECTOR);
  const trainingId = Number(panel?.dataset.trainingId || 0);
  if (!trainingId) return;
  const original = button.textContent;
  button.disabled = true; button.textContent = 'Editör hazırlanıyor…';
  try {
    const {source, detail} = await ensureSourceVersion(trainingId);
    const slides = editorSlides(detail?.manifest);
    if (!slides.length) throw new Error('Sunum manifestinde düzenlenebilir slayt bulunamadı.');
    const state = {trainingId, sourceId: Number(source.id), sourceVersion: Number(source.version || 0), selectedPosition: slides[0].position, kind: 'existing'};
    const overlay = document.createElement('div');
    overlay.className = 'training-presentation-editor';
    overlay.setAttribute('role', 'dialog'); overlay.setAttribute('aria-modal', 'true');
    overlay.innerHTML = `
      <section class="training-presentation-editor__shell">
        <header class="training-presentation-editor__head">
          <div><h3>Sunum Editörü · Ders Sunumu V3</h3><p>Kaynak v${state.sourceVersion} · değişiklikler yeni sürüm olarak kaydedilir; eski dosyalar korunur.</p></div>
          <button type="button" class="training-presentation-editor__close" data-editor-close>✕ Kapat</button>
        </header>
        <div class="training-presentation-editor__body">
          <aside class="training-presentation-editor__side">
            <h4>Slaytlar</h4>
            <div class="training-presentation-editor__slide-list">
              ${slides.map((slide, index) => `<button type="button" class="training-presentation-editor__slide${index === 0 ? ' is-active' : ''}" data-editor-slide="${slide.position}"><strong>${slide.position}. ${escapeHtml(slide.title)}</strong><small>${escapeHtml(slide.sectionId.replaceAll('_', ' '))}${slide.approvalRequired ? ' · onay' : ''}</small></button>`).join('')}
            </div>
          </aside>
          <main class="training-presentation-editor__form">${formMarkup(slides, state.selectedPosition)}</main>
        </div>
        <footer class="training-presentation-editor__foot">
          <span class="training-presentation-editor__status" data-editor-status>Kaydetme işlemi mevcut sürümü değiştirmez.</span>
          <div class="training-presentation-editor__actions">
            <button type="button" data-editor-save>Taslak olarak kaydet</button>
            <button type="button" class="is-v3" data-editor-render>Kaydet + Ders Sunumu V3 üret</button>
          </div>
        </footer>
      </section>`;
    overlay.addEventListener('click', (event) => {
      const slideButton = event.target.closest('[data-editor-slide]');
      if (slideButton) {
        state.kind = 'existing'; state.selectedPosition = Number(slideButton.dataset.editorSlide || 0);
        overlay.querySelectorAll('[data-editor-slide]').forEach((node) => node.classList.toggle('is-active', node === slideButton));
        overlay.querySelectorAll('[data-editor-kind]').forEach((node) => node.classList.toggle('is-active', node.dataset.editorKind === 'existing'));
        const slide = slides.find((item) => item.position === state.selectedPosition);
        overlay.querySelector('[data-editor-form-title]').textContent = `${slide.position}. slayt — geliştirme`;
        resetFields(overlay, slide);
        return;
      }
      const kindButton = event.target.closest('[data-editor-kind]');
      if (kindButton) {
        state.kind = kindButton.dataset.editorKind === 'new' ? 'new' : 'existing';
        overlay.querySelectorAll('[data-editor-kind]').forEach((node) => node.classList.toggle('is-active', node === kindButton));
        const slide = slides.find((item) => item.position === state.selectedPosition) || slides[0];
        overlay.querySelector('[data-editor-form-title]').textContent = state.kind === 'new' ? 'Yeni slayt ekle' : `${slide.position}. slayt — geliştirme`;
        resetFields(overlay, slide, {newSlide: state.kind === 'new'});
        return;
      }
      if (event.target === overlay || event.target.closest('[data-editor-close]')) closeEditor();
      if (event.target.closest('[data-editor-save]')) void saveEditor(overlay, state, {render: false});
      if (event.target.closest('[data-editor-render]')) void saveEditor(overlay, state, {render: true});
    });
    document.body.appendChild(overlay); document.body.style.overflow = 'hidden'; activeOverlay = overlay;
    overlay.querySelector('[data-editor-close]')?.focus();
  } catch (error) {
    window.alert(String(error?.message || error || 'Sunum editörü açılamadı.'));
  } finally {
    button.disabled = false; button.textContent = original;
  }
}

async function attachButtons() {
  const user = await currentUser();
  if (!canEditPresentationRole(user?.role)) return;
  document.querySelectorAll(PANEL_SELECTOR).forEach((panel) => {
    const actions = panel.querySelector('.training-presentation-panel__actions');
    if (!actions || actions.querySelector(`[${BUTTON_ATTR}]`)) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'training-presentation-panel__button training-presentation-editor-launch';
    button.setAttribute(BUTTON_ATTR, '');
    button.textContent = 'Sunumu Düzenle / V3';
    button.addEventListener('click', () => openEditor(button));
    actions.appendChild(button);
  });
}

function scheduleAttach() {
  if (timer) return;
  timer = window.setTimeout(() => { timer = null; void attachButtons(); }, 100);
}

observer = new MutationObserver(scheduleAttach);
observer.observe(document.documentElement, {childList: true, subtree: true});
scheduleAttach();

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    observer?.disconnect(); if (timer) window.clearTimeout(timer); closeEditor();
  });
}
