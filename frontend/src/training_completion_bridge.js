import {api} from './api';
import './training_completion_bridge.css';

const PANEL_SELECTOR = '.education-output-panel';
const BRIDGE_CLASS = 'training-completion-bridge';
const MODAL_ID = 'trainingCompletionModal';

function trainingIdFromPanel(panel) {
  const match = String(panel?.textContent || '').match(/Kayıt\s*#(\d+)/i);
  return match ? Number(match[1]) : null;
}

function certificateButton(panel) {
  return [...panel.querySelectorAll('button')].find((button) =>
    String(button.textContent || '').includes('Sertifika PDF'),
  );
}

function removeModal() {
  document.getElementById(MODAL_ID)?.remove();
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function resultLabel(row, passingScore) {
  if (!row.attended) return 'Katılmadı';
  if (row.score == null) return 'Puan bekleniyor';
  if (passingScore == null) return 'Geçme puanı eksik';
  return Number(row.score) >= Number(passingScore) ? 'Başarılı' : 'Başarısız';
}

function blockerText(preflight) {
  const blockers = Array.isArray(preflight?.training_blockers)
    ? preflight.training_blockers
    : [];
  return blockers.join(' ');
}

function updateBridgeStatus(panel, preflight) {
  const status = panel.querySelector(`.${BRIDGE_CLASS}__status`);
  const button = certificateButton(panel);
  const enforced = Boolean(preflight?.strict_enforced);
  const ready = Boolean(preflight?.ready_for_certificates);

  if (status) {
    status.classList.toggle('is-ready', enforced && ready);
    status.classList.toggle('is-blocked', enforced && !ready);
    if (!enforced) {
      status.textContent = 'Mevcut eğitim akışı korunuyor.';
    } else if (ready) {
      status.textContent = `${preflight.eligible_count || 0} kişi belge almaya hak kazandı.`;
    } else {
      status.textContent = blockerText(preflight) || 'Sonuçların kesinleştirilmesi gerekiyor.';
    }
  }

  if (button && enforced) {
    button.dataset.completionGuard = ready ? 'ready' : 'blocked';
    if (!ready) {
      button.disabled = true;
      button.title = blockerText(preflight) || 'Önce katılım ve sınav sonuçlarını kesinleştirin.';
    } else if (!String(button.textContent || '').includes('İndiriliyor')) {
      button.disabled = false;
      button.removeAttribute('title');
    }
  }
}

async function loadContext(trainingId) {
  const trainings = await api('/trainings');
  const training = Array.isArray(trainings)
    ? trainings.find((row) => Number(row.id) === Number(trainingId))
    : null;
  if (!training) throw new Error('Eğitim kaydı yüklenemedi.');

  const employees = await api(`/employees?company_id=${encodeURIComponent(training.company_id)}`);
  const employeeMap = new Map(
    (Array.isArray(employees) ? employees : []).map((employee) => [
      Number(employee.id),
      employee,
    ]),
  );
  const preflight = await api(`/trainings/${trainingId}/completion-preflight`);
  return {training, employeeMap, preflight};
}

function participantRows(context) {
  const preflightById = new Map(
    (context.preflight?.participants || []).map((row) => [Number(row.participant_id), row]),
  );
  return (context.training.participants || []).map((participant) => {
    const employee = context.employeeMap.get(Number(participant.employee_id));
    const audited = preflightById.get(Number(participant.id));
    return {
      ...participant,
      full_name: employee?.full_name || `Personel #${participant.employee_id}`,
      department: employee?.department || '',
      attended: Boolean(audited?.attended ?? participant.attended),
      score: audited?.score ?? participant.score ?? '',
      eligible: Boolean(audited?.eligible),
      reasons: audited?.reasons || [],
    };
  });
}

function renderModal(context, panel) {
  removeModal();
  const rows = participantRows(context);
  const examRequired = context.preflight?.exam_required !== false;
  const passingScore = context.training.passing_score;
  const blockers = context.preflight?.training_blockers || [];
  const warnings = context.preflight?.warnings || [];

  const overlay = document.createElement('div');
  overlay.id = MODAL_ID;
  overlay.className = 'training-completion-modal';
  overlay.innerHTML = `
    <div class="training-completion-modal__card" role="dialog" aria-modal="true" aria-labelledby="trainingCompletionTitle">
      <div class="training-completion-modal__header">
        <div>
          <h2 id="trainingCompletionTitle">Katılım ve sınav sonuçları</h2>
          <p>Eğitim #${context.training.id} · ${escapeHtml(context.training.title)} · Geçme puanı: ${passingScore ?? 'tanımlı değil'}</p>
        </div>
        <button type="button" class="training-completion-modal__close" aria-label="Kapat">×</button>
      </div>
      <div class="training-completion-modal__body">
        <div class="training-completion-summary">
          <div><strong>${context.preflight?.participant_total || rows.length}</strong><span>Toplam katılımcı</span></div>
          <div><strong>${context.preflight?.eligible_count || 0}</strong><span>Belgeye hak kazanan</span></div>
          <div><strong>${context.preflight?.ineligible_count || 0}</strong><span>Eksik / başarısız</span></div>
        </div>
        ${blockers.length ? `<div class="training-completion-alert">${blockers.map(escapeHtml).join('<br>')}</div>` : ''}
        ${warnings.length ? `<div class="training-completion-alert">${warnings.map(escapeHtml).join('<br>')}</div>` : ''}
        ${context.preflight?.ready_for_certificates ? '<div class="training-completion-alert is-success">Belge üretim koşulları tamamlandı.</div>' : ''}
        <div class="training-completion-table-wrap">
          <table class="training-completion-table">
            <thead><tr><th>Personel</th><th>Katıldı</th><th>${examRequired ? 'Puan' : 'Değerlendirme'}</th><th>Durum</th></tr></thead>
            <tbody>
              ${rows.map((row) => `
                <tr data-participant-id="${row.id}">
                  <td><strong>${escapeHtml(row.full_name)}</strong>${row.department ? `<br><small>${escapeHtml(row.department)}</small>` : ''}</td>
                  <td><input class="training-result-attended" type="checkbox" ${row.attended ? 'checked' : ''}></td>
                  <td>${examRequired ? `<input class="training-result-score" type="number" min="0" max="100" step="1" value="${escapeHtml(row.score)}" ${row.attended ? '' : 'disabled'}>` : 'Katılım esaslı'}</td>
                  <td class="training-result-state">${escapeHtml(resultLabel(row, passingScore))}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
        <div class="training-completion-alert" data-modal-message hidden></div>
      </div>
      <div class="training-completion-modal__actions">
        <button type="button" class="secondary" data-action="close">Kapat</button>
        <button type="button" class="save" data-action="save">Sonuçları Kaydet</button>
        <button type="button" class="finalize" data-action="finalize">Sonuçları Kesinleştir</button>
      </div>
    </div>`;

  document.body.appendChild(overlay);
  const message = overlay.querySelector('[data-modal-message]');
  const actionButtons = [...overlay.querySelectorAll('[data-action]')];

  function setBusy(busy) {
    actionButtons.forEach((button) => {
      button.disabled = busy;
    });
  }

  function showMessage(text, success = false) {
    message.hidden = false;
    message.textContent = text;
    message.classList.toggle('is-success', success);
  }

  function refreshRowState(rowElement) {
    const attended = rowElement.querySelector('.training-result-attended').checked;
    const scoreInput = rowElement.querySelector('.training-result-score');
    if (scoreInput) scoreInput.disabled = !attended;
    const score = scoreInput?.value === '' ? null : Number(scoreInput?.value);
    rowElement.querySelector('.training-result-state').textContent = resultLabel(
      {attended, score},
      passingScore,
    );
  }

  overlay.querySelectorAll('tbody tr').forEach((rowElement) => {
    rowElement.querySelector('.training-result-attended').addEventListener('change', () => {
      refreshRowState(rowElement);
    });
    rowElement.querySelector('.training-result-score')?.addEventListener('input', () => {
      refreshRowState(rowElement);
    });
  });

  async function saveResults() {
    const items = [...overlay.querySelectorAll('tbody tr')].map((rowElement) => {
      const attended = rowElement.querySelector('.training-result-attended').checked;
      const scoreInput = rowElement.querySelector('.training-result-score');
      return {
        participant_id: Number(rowElement.dataset.participantId),
        attended,
        score: attended && scoreInput?.value !== '' ? Number(scoreInput.value) : null,
      };
    });
    return api(`/trainings/${context.training.id}/participant-results`, {
      method: 'PUT',
      body: JSON.stringify({items}),
    });
  }

  overlay.querySelector('[data-action="save"]').addEventListener('click', async () => {
    setBusy(true);
    try {
      const preflight = await saveResults();
      updateBridgeStatus(panel, preflight);
      showMessage('Katılım ve sınav sonuçları kaydedildi. Kesinleştirme yapılmadan belge üretilemez.', true);
    } catch (error) {
      showMessage(error.message || 'Sonuçlar kaydedilemedi.');
    } finally {
      setBusy(false);
    }
  });

  overlay.querySelector('[data-action="finalize"]').addEventListener('click', async () => {
    setBusy(true);
    try {
      await saveResults();
      const preflight = await api(`/trainings/${context.training.id}/finalize`, {method: 'POST'});
      updateBridgeStatus(panel, preflight);
      showMessage(
        `Sonuçlar kesinleştirildi. ${preflight.eligible_count || 0} kişi belge almaya hak kazandı.`,
        true,
      );
    } catch (error) {
      showMessage(error.message || 'Eğitim sonuçları kesinleştirilemedi.');
    } finally {
      setBusy(false);
    }
  });

  overlay.querySelector('.training-completion-modal__close').addEventListener('click', removeModal);
  overlay.querySelector('[data-action="close"]').addEventListener('click', removeModal);
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) removeModal();
  });
}

async function openCompletion(trainingId, panel, button) {
  button.disabled = true;
  const originalText = button.textContent;
  button.textContent = 'Sonuçlar yükleniyor…';
  try {
    const context = await loadContext(trainingId);
    updateBridgeStatus(panel, context.preflight);
    renderModal(context, panel);
  } catch (error) {
    window.alert(error.message || 'Eğitim sonuçları yüklenemedi.');
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

async function attachBridge(panel) {
  const trainingId = trainingIdFromPanel(panel);
  if (!trainingId) return;
  const existing = panel.querySelector(`.${BRIDGE_CLASS}`);
  if (existing?.dataset.trainingId === String(trainingId)) return;
  existing?.remove();

  const bridge = document.createElement('div');
  bridge.className = BRIDGE_CLASS;
  bridge.dataset.trainingId = String(trainingId);
  bridge.innerHTML = `
    <div class="training-completion-bridge__row">
      <div>
        <strong>Katılım → sınav → başarı → belge kontrolü</strong>
        <div class="training-completion-bridge__status">Belge uygunluğu denetleniyor…</div>
      </div>
      <button type="button" class="training-completion-bridge__button">Katılım ve Sonuçları Yönet</button>
    </div>`;
  panel.appendChild(bridge);
  const button = bridge.querySelector('button');
  button.addEventListener('click', () => openCompletion(trainingId, panel, button));

  try {
    const preflight = await api(`/trainings/${trainingId}/completion-preflight`);
    if (panel.isConnected) updateBridgeStatus(panel, preflight);
  } catch {
    const status = bridge.querySelector(`.${BRIDGE_CLASS}__status`);
    if (status) status.textContent = 'Belge uygunluğu şu anda denetlenemedi.';
  }
}

function scan() {
  document.querySelectorAll(PANEL_SELECTOR).forEach((panel) => {
    attachBridge(panel);
  });
}

const observer = new MutationObserver(scan);
observer.observe(document.documentElement, {childList: true, subtree: true});
scan();
