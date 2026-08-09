import {api} from './api';
import {
  LIFECYCLE_STEPS,
  PREMIUM_TRAINING_TYPES,
  lifecycleTone,
  normalizePremiumPolicy,
  outputActionPolicy,
  parseTrainingIdFromText,
  ruleSummary,
  shouldReplacePrematureVerification,
} from './training_premium_lifecycle_logic';
import './training_premium_lifecycle.css';

let policy = null;
let policyPromise = null;
let observer = null;
let scanQueued = false;
const lifecycleCache = new Map();
const typeBound = new WeakSet();
const statusInFlight = new Set();

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

async function loadPolicy() {
  if (policy) return policy;
  if (!policyPromise) {
    policyPromise = api('/trainings/premium-policy')
      .then((raw) => {
        policy = normalizePremiumPolicy(raw);
        return policy;
      })
      .catch(() => {
        policy = normalizePremiumPolicy(null);
        return policy;
      });
  }
  return policyPromise;
}

function trainingRoot() {
  return document.querySelector('.training-pro');
}

function findControlByLabel(root, needle, selector = 'input,select,textarea') {
  const labels = [...root.querySelectorAll('label')];
  const label = labels.find((item) =>
    String(item.textContent || '').toLocaleLowerCase('tr').includes(needle.toLocaleLowerCase('tr')),
  );
  return label?.parentElement?.querySelector(selector) || null;
}

function setReactInputValue(input, value) {
  if (!input) return;
  const prototype = input instanceof HTMLSelectElement
    ? HTMLSelectElement.prototype
    : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
  if (setter) setter.call(input, value);
  else input.value = value;
  input.dispatchEvent(new Event('input', {bubbles: true}));
  input.dispatchEvent(new Event('change', {bubbles: true}));
}

function ensurePremiumTypeOptions(root) {
  const selects = [...root.querySelectorAll('select.tp-select')].filter((select) =>
    [...select.options].some((option) => option.textContent?.trim() === 'İlk Defa') &&
    [...select.options].some((option) => option.value === 'Tekrar'),
  );

  selects.forEach((select) => {
    PREMIUM_TRAINING_TYPES.forEach((item) => {
      if (![...select.options].some((option) => option.value === item.value)) {
        const option = document.createElement('option');
        option.value = item.value;
        option.textContent = item.label;
        select.appendChild(option);
      }
    });
    const repeat = [...select.options].find((option) => option.value === 'Tekrar');
    if (repeat) repeat.textContent = 'Tekrar Temel İSG Eğitimi · en az 8 ders saati';

    if (typeBound.has(select)) return;
    typeBound.add(select);
    select.addEventListener('change', () => {
      if (select.value !== 'İşe Başlama Eğitimi') return;
      const container = select.closest('.panel-card') || root;
      const title = findControlByLabel(container, 'Eğitimin adı', 'input');
      if (title) setReactInputValue(title, 'İşe Başlama İş Sağlığı ve Güvenliği Eğitimi');
      const evaluation = findControlByLabel(container, 'Başarı değerlendirmesi', 'select');
      if (evaluation && [...evaluation.options].some((option) => option.value === 'Katılım yeterlidir')) {
        setReactInputValue(evaluation, 'Katılım yeterlidir');
      }
    });
  });
}

function replacePrematureVerification(root) {
  if (!shouldReplacePrematureVerification(policy)) return;
  const boxes = [...root.querySelectorAll('label.check-box')].filter((label) => {
    const text = String(label.textContent || '');
    return text.includes('Katılım doğrulandı') || text.includes('Başarı koşulu sağlandı');
  });
  if (!boxes.length) return;
  boxes.forEach((label) => label.classList.add('training-premium-hidden-verification'));

  const parent = boxes[0].parentElement;
  if (!parent || parent.nextElementSibling?.classList?.contains('training-premium-policy-note')) return;
  const note = document.createElement('div');
  note.className = 'training-premium-policy-note';
  note.innerHTML = `
    <strong>Planlama aşaması:</strong>
    Katılım ve başarı şimdi onaylanmaz. Eğitimi kaydedin; eğitim yapıldıktan sonra
    <strong>Katılım ve Sonuçları Yönet</strong> ekranından gerçek katılımı ve varsa sınav puanlarını girin.
    Sistem yeni kayıtta katılım/başarı onaylarını otomatik olarak boş başlatır.`;
  parent.insertAdjacentElement('afterend', note);
}

function hazardClassFromRoot(root) {
  const control = findControlByLabel(root, 'Tehlike sınıfı', 'select,input');
  return control?.value || 'Çok Tehlikeli';
}

function renderPremiumHeader(root) {
  const tabs = root.querySelector('.tp-tabs');
  if (!tabs) return;
  const hazardClass = hazardClassFromRoot(root);
  const summary = ruleSummary(policy, hazardClass);
  let card = root.querySelector('.training-premium-lifecycle');
  if (!card) {
    card = document.createElement('section');
    card.className = 'training-premium-lifecycle';
    card.setAttribute('aria-label', 'Eğitim premium yaşam döngüsü');
    tabs.insertAdjacentElement('afterend', card);
  }
  const signature = JSON.stringify({hazardClass, summary});
  if (card.dataset.signature === signature) return;
  card.innerHTML = `
    <div class="training-premium-lifecycle__head">
      <div>
        <div class="training-premium-lifecycle__eyebrow">Eğitim Yönetim Merkezi</div>
        <h2>Planla → Gerçekleştir → Sonuçlandır → Belgelendir</h2>
        <p>
          Yeni eğitimler artık planlama aşamasında yanlışlıkla “katıldı / başarılı” kabul edilmez.
          İşe başlama, temel, tekrar ve bilgi yenileme eğitimleri ayrı kurallarla izlenir.
        </p>
      </div>
      <span class="training-premium-lifecycle__badge">✓ 2026 politika kontrolü aktif</span>
    </div>
    <div class="training-premium-lifecycle__steps">
      ${LIFECYCLE_STEPS.map((step, index) => `
        <div class="training-premium-lifecycle__step">
          <span>${index + 1}</span><span>${escapeHtml(step.label.replace(/^\d+\.\s*/, ''))}</span>
        </div>`).join('')}
    </div>
    <div class="training-premium-policy-note" style="margin-bottom:0">
      <strong>${escapeHtml(hazardClass)}:</strong>
      İlk temel eğitim ${summary.initialHours || '—'} ders saati ·
      tekrar temel eğitim ${summary.repeatHours || '—'} ders saati ·
      işe özgü bölüm en az ${summary.workSpecificHours || '—'} ders saati.
      ${escapeHtml(summary.lessonDefinition)}.
    </div>`;
  card.dataset.signature = signature;
}

async function lifecycleFor(trainingId) {
  if (lifecycleCache.has(trainingId)) return lifecycleCache.get(trainingId);
  const value = await api(`/trainings/${trainingId}/premium-lifecycle`);
  lifecycleCache.set(trainingId, value);
  return value;
}

function findOutputButton(panel, needle) {
  return [...panel.querySelectorAll('button')].find((button) =>
    String(button.textContent || '').includes(needle),
  ) || null;
}

function applyOutputActions(panel, lifecycle) {
  const actions = outputActionPolicy(lifecycle);
  const certificate = findOutputButton(panel, 'Sertifika PDF');
  const exam = findOutputButton(panel, 'Sınav Oluştur');
  const attendance = findOutputButton(panel, 'Katılım PDF') || findOutputButton(panel, 'İşe Başlama Eğitimi Tutanağı PDF');

  if (certificate) {
    if (certificate.dataset.premiumOriginalDisabled == null) {
      certificate.dataset.premiumOriginalDisabled = certificate.disabled ? '1' : '0';
    }
    certificate.disabled = !actions.certificateAllowed || certificate.dataset.premiumOriginalDisabled === '1';
    certificate.title = actions.certificateAllowed ? '' : actions.note;
  }
  if (exam) {
    if (exam.dataset.premiumOriginalDisabled == null) {
      exam.dataset.premiumOriginalDisabled = exam.disabled ? '1' : '0';
    }
    exam.disabled = !actions.examAllowed || exam.dataset.premiumOriginalDisabled === '1';
    exam.title = actions.examAllowed ? '' : actions.note;
  }
  if (attendance && actions.attendanceAllowed) {
    const icon = attendance.querySelector('svg')?.outerHTML || '';
    attendance.innerHTML = `${icon}${escapeHtml(actions.attendanceLabel)}`;
  }

  let note = panel.querySelector('[data-premium-output-note]');
  if (actions.note) {
    if (!note) {
      note = document.createElement('div');
      note.dataset.premiumOutputNote = '1';
      note.className = 'training-premium-policy-note';
      panel.appendChild(note);
    }
    note.textContent = actions.note;
  } else {
    note?.remove();
  }
}

async function renderSavedTrainingStatus(panel) {
  const trainingId = parseTrainingIdFromText(panel.textContent);
  if (!trainingId || statusInFlight.has(trainingId)) return;
  let card = panel.querySelector('.training-premium-status-card');
  if (card?.dataset.loaded === '1') return;

  if (!card) {
    card = document.createElement('div');
    card.className = 'training-premium-status-card is-info';
    card.innerHTML = '<div><strong>Yaşam döngüsü denetleniyor…</strong><span>Bir sonraki işlem belirleniyor.</span></div>';
    panel.appendChild(card);
  }

  statusInFlight.add(trainingId);
  try {
    lifecycleCache.delete(trainingId);
    const state = await lifecycleFor(trainingId);
    if (!panel.isConnected) return;
    applyOutputActions(panel, state);
    card.className = `training-premium-status-card is-${lifecycleTone(state.stage)}`;
    card.dataset.loaded = '1';
    card.innerHTML = `
      <div>
        <strong>${escapeHtml(state.stage_label || 'Eğitim durumu')}</strong>
        <span>${escapeHtml(state.next_action || '')}</span>
      </div>
      <span>${state.premium_enforced ? 'Yeni güvenli akış' : 'Tarihsel uyumluluk modu'}</span>`;
  } catch {
    card.innerHTML = '<div><strong>Yaşam döngüsü bilgisi alınamadı</strong><span>Mevcut eğitim işlemleri çalışmaya devam eder.</span></div>';
  } finally {
    statusInFlight.delete(trainingId);
  }
}

function scanOutputPanels(root) {
  root.querySelectorAll('section.education-output-panel').forEach((panel) => {
    renderSavedTrainingStatus(panel);
  });
}

function employeeMap(rows) {
  return new Map((Array.isArray(rows) ? rows : []).map((row) => [Number(row.id), row]));
}

async function resultContext(trainingId) {
  const trainings = await api('/trainings');
  const training = (Array.isArray(trainings) ? trainings : []).find((row) => Number(row.id) === Number(trainingId));
  if (!training) throw new Error('Eğitim kaydı yüklenemedi.');
  const [employees, preflight] = await Promise.all([
    api(`/employees?company_id=${encodeURIComponent(training.company_id)}`),
    api(`/trainings/${trainingId}/completion-preflight`),
  ]);
  return {training, employees: employeeMap(employees), preflight};
}

function resultLabel(attended, score, passingScore, examRequired) {
  if (!attended) return 'Katılmadı';
  if (!examRequired) return 'Katıldı';
  if (score == null || score === '') return 'Puan bekleniyor';
  if (passingScore == null) return 'Geçme puanı tanımlı değil';
  return Number(score) >= Number(passingScore) ? 'Başarılı' : 'Başarısız';
}

function closeResultModal() {
  document.querySelector('.training-premium-results-modal')?.remove();
  document.body.style.removeProperty('overflow');
}

async function openResultManager(trainingId, sourceButton) {
  sourceButton.disabled = true;
  const oldText = sourceButton.textContent;
  sourceButton.textContent = 'Sonuçlar yükleniyor…';
  try {
    const context = await resultContext(trainingId);
    const examRequired = context.preflight?.exam_required !== false;
    const passingScore = context.training.passing_score;
    const audited = new Map((context.preflight?.participants || []).map((row) => [Number(row.participant_id), row]));
    const rows = (context.training.participants || []).map((participant) => {
      const employee = context.employees.get(Number(participant.employee_id));
      const result = audited.get(Number(participant.id));
      return {
        ...participant,
        fullName: employee?.full_name || `Personel #${participant.employee_id}`,
        attended: Boolean(result?.attended ?? participant.attended),
        score: result?.score ?? participant.score ?? '',
      };
    });

    const overlay = document.createElement('div');
    overlay.className = 'training-premium-results-modal';
    overlay.innerHTML = `
      <section class="training-premium-results-modal__card" role="dialog" aria-modal="true" aria-labelledby="premiumResultsTitle">
        <header class="training-premium-results-modal__head">
          <div>
            <h2 id="premiumResultsTitle">Katılım ve Sonuçları Yönet</h2>
            <p>Kayıt #${context.training.id} · ${escapeHtml(context.training.title)} · Geçme puanı: ${passingScore ?? 'tanımlı değil'}</p>
          </div>
          <button type="button" class="training-premium-results-modal__close" aria-label="Kapat">×</button>
        </header>
        <div class="training-premium-results-modal__body">
          <div class="training-premium-policy-note">
            Önce gerçek katılımı ve ${examRequired ? 'sınav puanlarını' : 'değerlendirme durumunu'} kaydedin.
            <strong>Sonuçları Kesinleştir</strong> işlemi yapılmadan belge uygunluğu tamamlanmaz.
          </div>
          <div class="training-premium-results-modal__table-wrap">
            <table>
              <thead><tr><th>Personel</th><th>Katıldı</th><th>${examRequired ? 'Puan' : 'Değerlendirme'}</th><th>Durum</th></tr></thead>
              <tbody>
                ${rows.map((row) => `
                  <tr data-participant-id="${row.id}">
                    <td><strong>${escapeHtml(row.fullName)}</strong></td>
                    <td><input data-attended type="checkbox" ${row.attended ? 'checked' : ''}></td>
                    <td>${examRequired
                      ? `<input data-score type="number" min="0" max="100" step="1" value="${escapeHtml(row.score)}" ${row.attended ? '' : 'disabled'}>`
                      : 'Katılım esaslı'}</td>
                    <td data-state>${escapeHtml(resultLabel(row.attended, row.score, passingScore, examRequired))}</td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>
          <div class="training-premium-results-modal__message" data-message hidden></div>
        </div>
        <footer class="training-premium-results-modal__actions">
          <button type="button" data-action="close">Kapat</button>
          <button type="button" data-action="save">Sonuçları Kaydet</button>
          <button type="button" class="primary" data-action="finalize">Sonuçları Kesinleştir</button>
        </footer>
      </section>`;
    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';

    const message = overlay.querySelector('[data-message]');
    const actionButtons = [...overlay.querySelectorAll('[data-action]')];
    const setBusy = (busy) => actionButtons.forEach((button) => { button.disabled = busy; });
    const showMessage = (text, tone = '') => {
      message.hidden = false;
      message.textContent = text;
      message.className = `training-premium-results-modal__message${tone ? ` is-${tone}` : ''}`;
    };

    const refreshRow = (tr) => {
      const attended = tr.querySelector('[data-attended]').checked;
      const scoreInput = tr.querySelector('[data-score]');
      if (scoreInput) scoreInput.disabled = !attended;
      const score = scoreInput?.value === '' ? null : scoreInput?.value;
      tr.querySelector('[data-state]').textContent = resultLabel(attended, score, passingScore, examRequired);
    };
    overlay.querySelectorAll('tbody tr').forEach((tr) => {
      tr.querySelector('[data-attended]').addEventListener('change', () => refreshRow(tr));
      tr.querySelector('[data-score]')?.addEventListener('input', () => refreshRow(tr));
    });

    const payload = () => ({
      items: [...overlay.querySelectorAll('tbody tr')].map((tr) => {
        const attended = tr.querySelector('[data-attended]').checked;
        const scoreInput = tr.querySelector('[data-score]');
        return {
          participant_id: Number(tr.dataset.participantId),
          attended,
          score: examRequired && attended && scoreInput?.value !== '' ? Number(scoreInput.value) : null,
        };
      }),
    });

    async function save() {
      return api(`/trainings/${trainingId}/participant-results`, {
        method: 'PUT',
        body: JSON.stringify(payload()),
      });
    }

    overlay.querySelector('[data-action="save"]').addEventListener('click', async () => {
      setBusy(true);
      try {
        await save();
        lifecycleCache.delete(trainingId);
        showMessage('Katılım ve sonuçlar kaydedildi. Şimdi sonuçları kesinleştirebilirsiniz.', 'success');
      } catch (error) {
        showMessage(error.message || 'Sonuçlar kaydedilemedi.', 'error');
      } finally {
        setBusy(false);
      }
    });

    overlay.querySelector('[data-action="finalize"]').addEventListener('click', async () => {
      setBusy(true);
      try {
        await save();
        const result = await api(`/trainings/${trainingId}/finalize`, {method: 'POST'});
        lifecycleCache.delete(trainingId);
        sourceButton.textContent = '✓ Eğitim tamamlandı';
        sourceButton.disabled = true;
        showMessage(`Sonuçlar kesinleştirildi. ${result.eligible_count || 0} kişi belge almaya hak kazandı.`, 'success');
      } catch (error) {
        showMessage(error.message || 'Eğitim sonuçları kesinleştirilemedi.', 'error');
      } finally {
        setBusy(false);
      }
    });

    overlay.querySelector('[data-action="close"]').addEventListener('click', closeResultModal);
    overlay.querySelector('.training-premium-results-modal__close').addEventListener('click', closeResultModal);
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closeResultModal();
    });
    overlay.querySelector('.training-premium-results-modal__close')?.focus();
  } catch (error) {
    window.alert(error.message || 'Katılım ve sonuç ekranı açılamadı.');
  } finally {
    if (!String(sourceButton.textContent || '').includes('tamamlandı')) {
      sourceButton.disabled = false;
      sourceButton.textContent = oldText;
    }
  }
}

function interceptLegacyCompletion(event) {
  const button = event.target.closest('button');
  if (!button || !String(button.textContent || '').includes('Eğitimi Tamamla')) return;
  const card = button.closest('.panel-card');
  const trainingId = parseTrainingIdFromText(card?.textContent || '');
  if (!trainingId) return;
  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();
  openResultManager(trainingId, button);
}

function scanNow() {
  scanQueued = false;
  if (!policy?.enabled) return;
  const root = trainingRoot();
  if (!root) return;
  renderPremiumHeader(root);
  ensurePremiumTypeOptions(root);
  replacePrematureVerification(root);
  scanOutputPanels(root);
}

function queueScan() {
  if (scanQueued) return;
  scanQueued = true;
  queueMicrotask(scanNow);
}

async function start() {
  const loaded = await loadPolicy();
  if (!loaded.enabled) return;
  document.addEventListener('click', interceptLegacyCompletion, true);
  observer = new MutationObserver(queueScan);
  observer.observe(document.documentElement, {childList: true, subtree: true});
  queueScan();
}

start();