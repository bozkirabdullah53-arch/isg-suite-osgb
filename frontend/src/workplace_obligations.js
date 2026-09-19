const STATUS_LABELS = Object.freeze({
  overdue: 'Gecikmiş',
  very_soon: 'Çok Yakın',
  approaching: 'Yaklaşıyor',
  scheduled: 'İleri Tarihli',
  completed: 'Tamamlandı',
});

const SELECTED_OBLIGATION_KEY = 'isg_workplace_selected_obligation';

function isoDate(value) {
  const date = value instanceof Date ? new Date(value.getTime()) : new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function defaultObligationFilters(now = new Date()) {
  const until = new Date(now.getTime());
  until.setDate(until.getDate() + 30);
  return {
    branch_id: '',
    category: '',
    status: '',
    date_from: '',
    date_to: isoDate(until),
  };
}

export function buildObligationQuery(filters = {}, page = 1, pageSize = 25) {
  const params = new URLSearchParams({page: String(page), page_size: String(pageSize)});
  for (const key of ['branch_id', 'category', 'status', 'date_from', 'date_to']) {
    const value = String(filters[key] ?? '').trim();
    if (value) params.set(key, value);
  }
  return params.toString();
}

export function obligationStatusLabel(status) {
  return STATUS_LABELS[status] || status || 'Belirsiz';
}

export function obligationDaysText(row) {
  if (row?.status === 'completed') return 'Tamamlandı';
  const days = Number(row?.days_left);
  if (!Number.isFinite(days)) return '—';
  if (days < 0) return `${Math.abs(days)} gün gecikti`;
  if (days === 0) return 'Bugün';
  return `${days} gün kaldı`;
}

export function rememberSelectedObligation(row) {
  if (!row || typeof sessionStorage === 'undefined') return;
  try {
    sessionStorage.setItem(SELECTED_OBLIGATION_KEY, JSON.stringify(row));
  } catch (_) {
    // Private browsing / storage quota must not block navigation.
  }
}

export function consumeSelectedObligation(companyId) {
  if (typeof sessionStorage === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(SELECTED_OBLIGATION_KEY);
    if (!raw) return null;
    const row = JSON.parse(raw);
    if (String(row?.company_id || row?.target?.company_id || '') !== String(companyId || '')) {
      return null;
    }
    sessionStorage.removeItem(SELECTED_OBLIGATION_KEY);
    return row;
  } catch (_) {
    sessionStorage.removeItem(SELECTED_OBLIGATION_KEY);
    return null;
  }
}

export {STATUS_LABELS as WORKPLACE_OBLIGATION_STATUS_LABELS};
