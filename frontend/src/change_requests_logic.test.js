import {describe, expect, it} from 'vitest';
import {
  allowedActions,
  canApprove,
  canApply,
  canCancel,
  canVerify,
  canViewRequest,
  channelLabel,
  dataSubjectKindOptions,
  entityTypeLabel,
  isOpenStatus,
  isTerminalStatus,
  requestKindLabel,
  requesterTypeLabel,
  slaLabel,
  slaState,
  statusLabel,
} from './change_requests_logic';

const globalAdmin = {id: 10, role: 'global_admin', company_id: null};
const companyAdmin = {id: 20, role: 'company_admin', company_id: 5};

function request(overrides = {}) {
  return {
    id: 1,
    request_no: 'CR-2026-0001',
    company_id: 5,
    requested_by_user_id: 20,
    verified_by_id: 10,
    approved_by_id: 11,
    applied_by_id: null,
    status: 'submitted',
    sla_due_at: '2026-10-01T00:00:00Z',
    requester_type: 'employer',
    request_kind: null,
    channel: 'platform',
    target_entity_type: 'employee',
    ...overrides,
  };
}

describe('change request labels', () => {
  it('translates statuses', () => {
    expect(statusLabel('submitted')).toBe('Talep Alındı');
    expect(statusLabel('applied')).toBe('Uygulandı');
    expect(statusLabel(null)).toBe('—');
  });

  it('translates requester types, kinds, channels and entities', () => {
    expect(requesterTypeLabel('data_subject')).toBe('Veri Sahibi (KVKK)');
    expect(requestKindLabel('erasure')).toBe('Silme Talebi');
    expect(channelLabel('official_letter')).toBe('Resmî Yazı');
    expect(entityTypeLabel('incident')).toBe('Olay / İş Kazası');
  });

  it('exposes KVKK kind options', () => {
    const options = dataSubjectKindOptions();
    expect(options.map((item) => item.value)).toEqual(['access', 'rectification', 'erasure', 'portability']);
  });
});

describe('change request status helpers', () => {
  it('classifies open and terminal states', () => {
    expect(isOpenStatus('submitted')).toBe(true);
    expect(isOpenStatus('approved')).toBe(true);
    expect(isOpenStatus('applied')).toBe(false);
    expect(isTerminalStatus('rejected')).toBe(true);
    expect(isTerminalStatus('verified')).toBe(false);
  });
});

describe('change request visibility', () => {
  it('lets global admin see everything', () => {
    expect(canViewRequest(request({company_id: 999}), globalAdmin)).toBe(true);
  });

  it('scopes other users to their company or own request', () => {
    expect(canViewRequest(request(), companyAdmin)).toBe(true);
    expect(canViewRequest(request({company_id: 7, requested_by_user_id: 99}), companyAdmin)).toBe(false);
  });
});

describe('four-eyes enforcement in the UI', () => {
  it('does not let the requester approve', () => {
    const row = request({status: 'verified', requested_by_user_id: 10, verified_by_id: 11});
    expect(canApprove(row, globalAdmin)).toBe(false);
  });

  it('does not let the verifier approve', () => {
    const row = request({status: 'verified', requested_by_user_id: 20, verified_by_id: 10});
    expect(canApprove(row, globalAdmin)).toBe(false);
  });

  it('allows an unrelated global admin to approve', () => {
    const row = request({status: 'verified', requested_by_user_id: 20, verified_by_id: 11});
    expect(canApprove(row, globalAdmin)).toBe(true);
  });

  it('does not let the approver apply', () => {
    const row = request({status: 'approved', approved_by_id: 10});
    expect(canApply(row, globalAdmin)).toBe(false);
  });

  it('allows an unrelated global admin to apply', () => {
    const row = request({status: 'approved', approved_by_id: 11});
    expect(canApply(row, globalAdmin)).toBe(true);
  });

  it('restricts approval and apply to global admins', () => {
    const row = request({status: 'verified'});
    expect(canApprove(row, companyAdmin)).toBe(false);
    expect(canApply({...row, status: 'approved'}, companyAdmin)).toBe(false);
  });
});

describe('change request actions', () => {
  it('lists actions for a fresh submission', () => {
    const row = request({status: 'submitted', requested_by_user_id: 99});
    expect(allowedActions(row, globalAdmin)).toEqual(['verify', 'reject', 'cancel']);
  });

  it('lists actions for a verified request', () => {
    const row = request({status: 'verified', requested_by_user_id: 99, verified_by_id: 11});
    expect(allowedActions(row, globalAdmin)).toEqual(['approve', 'reject', 'cancel']);
  });

  it('lists actions for an approved request', () => {
    const row = request({status: 'approved', requested_by_user_id: 99, approved_by_id: 11});
    expect(allowedActions(row, globalAdmin)).toEqual(['reject', 'apply', 'cancel']);
  });

  it('gives the requester cancel rights', () => {
    const row = request({status: 'submitted', requested_by_user_id: 20});
    expect(canCancel(row, companyAdmin)).toBe(true);
    expect(canVerify(row, companyAdmin)).toBe(true);
  });

  it('returns no actions for a terminal request', () => {
    expect(allowedActions(request({status: 'applied'}), globalAdmin)).toEqual([]);
  });
});

describe('SLA tracking', () => {
  const now = new Date('2026-09-21T00:00:00Z');

  it('reports on-time requests', () => {
    expect(slaState(request({sla_due_at: '2026-10-01T00:00:00Z'}), now).state).toBe('ontime');
  });

  it('reports soon when under three days remain', () => {
    expect(slaState(request({sla_due_at: '2026-09-23T00:00:00Z'}), now).state).toBe('soon');
  });

  it('reports overdue requests', () => {
    const state = slaState(request({sla_due_at: '2026-09-01T00:00:00Z'}), now);
    expect(state.state).toBe('overdue');
    expect(slaLabel(request({sla_due_at: '2026-09-01T00:00:00Z'}), now)).toContain('gecikti');
  });

  it('closes SLA tracking for terminal requests', () => {
    expect(slaState(request({status: 'applied', sla_due_at: '2026-09-01T00:00:00Z'}), now).state).toBe('closed');
  });

  it('handles missing SLA', () => {
    expect(slaState(request({sla_due_at: null}), now).state).toBe('none');
    expect(slaLabel(request({sla_due_at: null}), now)).toBe('—');
  });
});
