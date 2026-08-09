import {api} from './api';
import {
  actionTargetLabel,
  dashboardHeadline,
  normalizeTrainingDashboard,
  statusTone,
} from './training_premium_dashboard_logic';
import './training_premium_dashboard.css';

const ID = 'trainingPremiumDashboardV1';
const REFRESH_TTL_MS = 30_000;
let observer = null;
let queued = false;
let inFlight = false;
let lastCompanyId = null;
let lastFetchAt = 0;
let lastSignature = '';
let forceNextRefresh = false;

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function trainingRoot() {
  return document.querySelector('.training-pro');
}

function selectedCompanyId(root) {
  const value = Number(root?.querySelector('#tp-firma')?.value || 0);
  return value > 0 ? value : null;
}

function removeDashboard() {
  document.getElementById(ID)?.remove();
  lastSignature = '';
}

function statusHtml(value) {
  const state = value && typeof value === 'object' ? value : {};
  return `<span class="training-premium-dashboard__status is-${statusTone(state.tone)}">${escapeHtml(state.label || 'Bilinmiyor')}</span>`;
}

function switchTab(target) {
  const root = trainingRoot();
  const label = actionTargetLabel(target);
  const button = [...(root?.querySelectorAll('.tp-tab') || [])].find(
    (item) => String(item.textContent || '').trim() === label,
  );
  button?.click();
  if (button) window.setTimeout(() => root?.scrollIntoView({behavior: 'smooth', block: 'start'}), 50);
}

function attachInteractions(section) {
  if (section.dataset.interactionsBound === '1') return;
  section.dataset.interactionsBound = '1';
  section.addEventListener('click', (event) => {
    const action = event.target.closest('[data-dashboard-target]');
    if (action) switchTab(action.dataset.dashboardTarget);

    const toggle = event.target.closest('[data-dashboard-toggle]');
    if (toggle) {
      const rows = section.querySelector('[data-dashboard-rows]');
      const opening = Boolean(rows?.hidden);
      if (rows) rows.hidden = !opening;
      toggle.textContent = opening ? 'Çalışan durumlarını gizle' : 'Çalışan durumlarını göster';
    }

    if (event.target.closest('[data-dashboard-refresh]')) {
      forceNextRefresh = true;
      queueScan();
    }
  });
}

function ensureSection(root) {
  let section = document.getElementById(ID);
  if (section) return section;
  const anchor = root.querySelector('.training-premium-lifecycle') || root.querySelector('.tp-tabs');
  if (!anchor) return null;
  section = document.createElement('section');
  section.id = ID;
  section.className = 'training-premium-dashboard';
  anchor.insertAdjacentElement('afterend', section);
  attachInteractions(section);
  return section;
}

function render(root, dashboard) {
  const section = ensureSection(root);
  if (!section) return;
  const headline = dashboardHeadline(dashboard.summary);
  const signature = JSON.stringify({
    companyId: dashboard.companyId,
    summary: dashboard.summary,
    actions: dashboard.actions,
    rows: dashboard.rows,
  });
  if (signature === lastSignature && section.dataset.companyId === String(dashboard.companyId || '')) return;

  const actionHtml = dashboard.actions.length
    ? dashboard.actions.map((action) => `
      <button type="button" class="training-premium-dashboard__action is-${escapeHtml(action.severity)}" data-dashboard-target="${escapeHtml(action.target)}">
        <span class="training-premium-dashboard__count">${Number(action.count || 0)}</span>
        <strong>${escapeHtml(action.title)}</strong>
        <span>${escapeHtml(action.instruction)}</span>
        <span style="margin-top:8px;font-weight:800">→ ${escapeHtml(actionTargetLabel(action.target))}</span>
      </button>`).join('')
    : '<div class="training-premium-dashboard__empty">Bugün için acil eğitim işlemi görünmüyor. Mevcut planları ve yenileme tarihlerini yine de kontrol edebilirsiniz.</div>';

  const rowHtml = dashboard.rows.map((row) => `
    <tr>
      <td class="training-premium-dashboard__person">
        <strong>${escapeHtml(row.full_name)}</strong>
        <span>${escapeHtml([row.job_title, row.department].filter(Boolean).join(' · ') || 'Görev / bölüm belirtilmemiş')}</span>
      </td>
      <td>${escapeHtml(row.start_date || '—')}</td>
      <td>${statusHtml(row.work_start)}<div class="training-premium-dashboard__message">${escapeHtml(row.work_start?.message || '')}</div></td>
      <td>${statusHtml(row.basic)}<div class="training-premium-dashboard__message">${escapeHtml(row.basic?.message || '')}</div></td>
    </tr>`).join('');

  section.dataset.companyId = String(dashboard.companyId || '');
  section.innerHTML = `
    <div class="training-premium-dashboard__head">
      <div>
        <div class="training-premium-dashboard__eyebrow">Bugün Ne Yapmalıyım?</div>
        <h2>Eğitim işlerini önem sırasına koyduk</h2>
        <p>Kırmızıları önce, sarıları sonra tamamlayın. Sistem hiçbir eğitimi sizin yerinize otomatik tamamlamaz.</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <span class="training-premium-dashboard__headline is-${headline.tone}">${escapeHtml(headline.label)}</span>
        <button type="button" class="training-premium-dashboard__toggle" style="margin-top:0" data-dashboard-refresh>Yenile</button>
      </div>
    </div>
    <div class="training-premium-dashboard__actions">${actionHtml}</div>
    <div class="training-premium-dashboard__summary">
      <div class="training-premium-dashboard__metric"><strong>${Number(dashboard.summary.active_employees || 0)}</strong><span>Aktif çalışan</span></div>
      <div class="training-premium-dashboard__metric"><strong>${Number(dashboard.summary.work_start_missing || 0)}</strong><span>İşe Başlama eksik</span></div>
      <div class="training-premium-dashboard__metric"><strong>${Number(dashboard.summary.basic_overdue || 0)}</strong><span>Temel eğitim gecikmiş / eksik</span></div>
      <div class="training-premium-dashboard__metric"><strong>${Number(dashboard.summary.basic_ok || 0)}</strong><span>Temel eğitim geçerli</span></div>
    </div>
    <button type="button" class="training-premium-dashboard__toggle" data-dashboard-toggle>Çalışan durumlarını göster</button>
    <div class="training-premium-dashboard__table-wrap" data-dashboard-rows hidden>
      <table>
        <thead><tr><th>Çalışan</th><th>İşe giriş</th><th>İşe Başlama Eğitimi</th><th>Temel İSG Eğitimi</th></tr></thead>
        <tbody>${rowHtml || '<tr><td colspan="4">Aktif çalışan bulunamadı.</td></tr>'}</tbody>
      </table>
    </div>`;
  attachInteractions(section);
  lastSignature = signature;
}

async function refresh(root, companyId) {
  if (inFlight) return;
  const now = Date.now();
  const sameCompany = Number(lastCompanyId) === Number(companyId);
  if (!forceNextRefresh && sameCompany && now - lastFetchAt < REFRESH_TTL_MS) return;

  inFlight = true;
  forceNextRefresh = false;
  try {
    const dashboard = normalizeTrainingDashboard(
      await api(`/trainings/premium-dashboard?company_id=${encodeURIComponent(companyId)}`),
    );
    lastFetchAt = Date.now();
    lastCompanyId = companyId;
    if (!dashboard.enabled || !trainingRoot()) {
      removeDashboard();
      return;
    }
    render(root, dashboard);
  } catch {
    // Purely additive: dashboard read failure must never break the existing Training page.
  } finally {
    inFlight = false;
  }
}

function scan() {
  queued = false;
  const root = trainingRoot();
  if (!root) {
    removeDashboard();
    return;
  }
  const companyId = selectedCompanyId(root);
  if (!companyId) {
    // Important: do not render even a placeholder before the feature endpoint is queried.
    // This keeps feature-OFF behavior visually identical to the existing Training page.
    lastCompanyId = null;
    lastFetchAt = 0;
    removeDashboard();
    return;
  }
  refresh(root, companyId);
}

function queueScan() {
  if (queued) return;
  queued = true;
  window.setTimeout(scan, 0);
}

document.addEventListener('change', (event) => {
  if (event.target?.matches?.('#tp-firma')) {
    lastCompanyId = null;
    lastFetchAt = 0;
    lastSignature = '';
    forceNextRefresh = true;
    queueScan();
  }
});

document.addEventListener('click', (event) => {
  const text = String(event.target.closest('button')?.textContent || '');
  if (/Kaydet|Kesinleştir|Tamamla|Eğitime aktar/i.test(text)) {
    window.setTimeout(() => {
      forceNextRefresh = true;
      queueScan();
    }, 1200);
  }
});

observer = new MutationObserver(queueScan);
observer.observe(document.documentElement, {childList: true, subtree: true});
queueScan();
