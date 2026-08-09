import {api} from './api';
import {canEditPresentationRole, pickEditableVersion} from './training_presentation_editor_logic';

const PANEL_SELECTOR = '.training-presentation-panel[data-training-id]';
const BUTTON_ATTR = 'data-presentation-v3-upgrade';
let currentUserPromise = null;
let observer = null;
let timer = null;

async function currentUser() {
  if (!currentUserPromise) {
    currentUserPromise = api('/auth/me')
      .then((user) => {
        if (!user?.role) currentUserPromise = null;
        return user;
      })
      .catch(() => {
        currentUserPromise = null;
        return null;
      });
  }
  return currentUserPromise;
}

async function sourceVersion(trainingId) {
  let history = await api(`/trainings/${trainingId}/presentation-versions`);
  let source = pickEditableVersion(history?.rows);
  if (!source) {
    source = await api(`/trainings/${trainingId}/presentation-versions`, {method: 'POST'});
    history = await api(`/trainings/${trainingId}/presentation-versions`);
    source = pickEditableVersion(history?.rows) || source;
  }
  if (!source?.id) throw new Error('V3 için kaynak sunum sürümü oluşturulamadı.');
  return source;
}

async function upgrade(button) {
  const panel = button.closest(PANEL_SELECTOR);
  const trainingId = Number(panel?.dataset.trainingId || 0);
  if (!trainingId) return;
  const original = button.textContent;
  button.disabled = true;
  button.textContent = 'V3 hazırlanıyor…';
  try {
    const source = await sourceVersion(trainingId);
    const created = await api(
      `/trainings/${trainingId}/presentation-versions/${source.id}/edit-copy`,
      {
        method: 'POST',
        body: JSON.stringify({
          slide_updates: [],
          append_slides: [],
          change_note: 'Mevcut doğrulanmış sunum içeriği Ders Sunumu V3 olarak zenginleştirildi.',
          auto_enrich_teaching_v3: true,
        }),
      },
    );
    await api(`/trainings/${trainingId}/presentation-versions/${created.id}/render-teaching-v3`, {method: 'POST'});
    window.alert(`Ders Sunumu V3 v${created.version} oluşturuldu. Eski sunum sürümleri aynen korundu.`);
    window.dispatchEvent(new CustomEvent('isgsuite:presentation-refresh', {
      detail: {trainingId, versionId: created.id},
    }));
    button.disabled = false;
    button.textContent = original;
  } catch (error) {
    window.alert(String(error?.message || error || 'Ders Sunumu V3 oluşturulamadı.'));
    button.disabled = false;
    button.textContent = original;
  }
}

async function attach() {
  const user = await currentUser();
  if (!canEditPresentationRole(user?.role)) return;
  document.querySelectorAll(PANEL_SELECTOR).forEach((panel) => {
    const actions = panel.querySelector('.training-presentation-panel__actions');
    if (!actions || actions.querySelector(`[${BUTTON_ATTR}]`)) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'training-presentation-panel__button training-presentation-editor-launch';
    button.setAttribute(BUTTON_ATTR, '');
    button.textContent = 'Ders Sunumu V3 Oluştur';
    button.title = 'Mevcut doğrulanmış içeriği görsel ve öğretici Ders Sunumu V3 sürümüne dönüştürür; eski sürümü değiştirmez.';
    button.addEventListener('click', () => void upgrade(button));
    actions.appendChild(button);
  });
}

function schedule() {
  if (timer) return;
  timer = window.setTimeout(() => { timer = null; void attach(); }, 100);
}

observer = new MutationObserver(schedule);
observer.observe(document.documentElement, {childList: true, subtree: true});
schedule();

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    observer?.disconnect();
    if (timer) window.clearTimeout(timer);
  });
}
