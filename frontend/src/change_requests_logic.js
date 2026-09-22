/**
 * İBYS Değişiklik Talebi arayüz mantığı (§3-§5).
 *
 * Backend 4 göz prensibini zorlar; burada aynı kural UX için uygulanır:
 * kullanıcı kendi talebini onaylayamaz, doğrulayan onaylayamaz,
 * onaylayan uygulayamaz.
 */

export const CHANGE_REQUEST_STATUSES = ['submitted', 'verified', 'approved', 'applied', 'rejected', 'cancelled'];

export const CHANGE_REQUEST_STATUS_LABELS = {
  submitted: 'Talep Alındı',
  verified: 'Doğrulandı',
  approved: 'Onaylandı',
  applied: 'Uygulandı',
  rejected: 'Reddedildi',
  cancelled: 'İptal Edildi',
};

export const REQUESTER_TYPE_LABELS = {
  data_subject: 'Veri Sahibi (KVKK)',
  employer: 'İşveren / İşyeri',
  internal: 'Kurum İçi',
};

export const REQUEST_KIND_LABELS = {
  access: 'Veri Erişim Talebi',
  rectification: 'Düzeltme Talebi',
  erasure: 'Silme Talebi',
  portability: 'Veri Taşınabilirliği',
};

export const CHANNEL_LABELS = {
  platform: 'Platform',
  email: 'E-posta',
  official_letter: 'Resmî Yazı',
};

export const ENTITY_TYPE_LABELS = {
  employee: 'Personel',
  company: 'İşyeri',
  incident: 'Olay / İş Kazası',
};

export function statusLabel(status) {
  return CHANGE_REQUEST_STATUS_LABELS[status] || status || '—';
}

export function requesterTypeLabel(value) {
  return REQUESTER_TYPE_LABELS[value] || value || '—';
}

export function requestKindLabel(value) {
  return REQUEST_KIND_LABELS[value] || '—';
}

export function channelLabel(value) {
  return CHANNEL_LABELS[value] || value || '—';
}

export function entityTypeLabel(value) {
  return ENTITY_TYPE_LABELS[value] || value || '—';
}

export function isOpenStatus(status) {
  return ['submitted', 'verified', 'approved'].includes(status);
}

export function isTerminalStatus(status) {
  return ['applied', 'rejected', 'cancelled'].includes(status);
}

/** Global yönetici tüm talepleri görür; diğerleri kendi firması veya kendi talebi. */
export function canViewRequest(request, user) {
  if (!request || !user) return false;
  if (user.role === 'global_admin') return true;
  if (request.requested_by_user_id === user.id) return true;
  return Boolean(user.company_id) && request.company_id === user.company_id;
}

export function canVerify(request, user) {
  if (!request || !user) return false;
  if (!isOpenStatus(request.status)) return false;
  if (!['global_admin', 'company_admin'].includes(user.role)) return false;
  return request.status === 'submitted';
}

export function canApprove(request, user) {
  if (!request || !user) return false;
  if (request.status !== 'verified') return false;
  if (user.role !== 'global_admin') return false;
  // 4 göz: talep eden ve doğrulayan onaylayamaz.
  if (request.requested_by_user_id === user.id) return false;
  if (request.verified_by_id === user.id) return false;
  return true;
}

export function canReject(request, user) {
  if (!request || !user) return false;
  if (!isOpenStatus(request.status)) return false;
  if (!['global_admin', 'company_admin'].includes(user.role)) return false;
  return true;
}

export function canApply(request, user) {
  if (!request || !user) return false;
  if (request.status !== 'approved') return false;
  if (user.role !== 'global_admin') return false;
  // 4 göz: onaylayan kişi uygulayamaz.
  return request.approved_by_id !== user.id;
}

export function canCancel(request, user) {
  if (!request || !user) return false;
  if (!isOpenStatus(request.status)) return false;
  if (user.role === 'global_admin') return true;
  return request.requested_by_user_id === user.id;
}

export function allowedActions(request, user) {
  const actions = [];
  if (canVerify(request, user)) actions.push('verify');
  if (canApprove(request, user)) actions.push('approve');
  if (canReject(request, user)) actions.push('reject');
  if (canApply(request, user)) actions.push('apply');
  if (canCancel(request, user)) actions.push('cancel');
  return actions;
}

/** SLA durumu: açık talebin son tarihi geçti mi? */
export function slaState(request, now = new Date()) {
  if (!request || !request.sla_due_at) return {state: 'none', daysLeft: null};
  const due = new Date(request.sla_due_at);
  if (Number.isNaN(due.getTime())) return {state: 'none', daysLeft: null};
  const diffMs = due.getTime() - now.getTime();
  const daysLeft = Math.ceil(diffMs / 86400000);
  if (isTerminalStatus(request.status)) return {state: 'closed', daysLeft};
  if (diffMs < 0) return {state: 'overdue', daysLeft};
  if (daysLeft <= 3) return {state: 'soon', daysLeft};
  return {state: 'ontime', daysLeft};
}

export function slaLabel(request, now = new Date()) {
  const {state, daysLeft} = slaState(request, now);
  if (state === 'none') return '—';
  if (state === 'closed') return 'Kapatıldı';
  if (state === 'overdue') return `${Math.abs(daysLeft)} gün gecikti`;
  if (daysLeft === 0) return 'Bugün son gün';
  return `${daysLeft} gün kaldı`;
}

export function formatDateTime(value) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleString('tr-TR');
}

/** KVKK veri sahibi talebi için başvuru türü seçenekleri. */
export function dataSubjectKindOptions() {
  return Object.entries(REQUEST_KIND_LABELS).map(([value, label]) => ({value, label}));
}
