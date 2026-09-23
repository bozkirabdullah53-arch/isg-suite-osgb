import {describe, expect, it} from 'vitest';
import {canOpenCompanyCapa, normalizeCompanyId} from './company_module_navigation';
import {
  NAVIGATION_STATE_KEY,
  createNavigationState,
  navigationIndex,
  nextNavigationIndex,
  parseNavigationLocation,
} from './navigation_history';

describe('navigation history compatibility', () => {
  it('reads current, legacy hash and query module links', () => {
    expect(parseNavigationLocation({hash: '#m=risk'})).toEqual({module: 'risk', companyId: ''});
    expect(parseNavigationLocation({hash: '#/risk'})).toEqual({module: 'risk', companyId: ''});
    expect(parseNavigationLocation({search: '?m=risk&company_id=42'})).toEqual({module: 'risk', companyId: '42'});
    expect(parseNavigationLocation({hash: '#m=customer_360&company=42'})).toEqual({module: 'customer_360', companyId: '42'});
  });

  it('preserves the route index when replacing and increments it when pushing', () => {
    const initial = createNavigationState({other: 'keep'}, {module: 'dashboard', index: 0});
    expect(initial).toMatchObject({
      other: 'keep',
      [NAVIGATION_STATE_KEY]: true,
      module: 'dashboard',
      navigationIndex: 0,
    });
    expect(nextNavigationIndex(initial)).toBe(1);
    expect(nextNavigationIndex(initial, {replace: true})).toBe(0);
    expect(navigationIndex(initial)).toBe(0);
  });

  it('keeps company context only on supported routes', () => {
    const detail = createNavigationState(null, {
      module: 'customer_360',
      companyId: 42,
      index: 2,
    });
    expect(detail.companyId).toBe('42');
    expect(createNavigationState(detail, {module: 'risk', index: 3}).companyId).toBeUndefined();
    for (const module of ['customer_360', 'capa', 'workplace_status', 'osgb_dashboard']) {
      expect(createNavigationState(detail, {module, companyId: 42}).companyId).toBe('42');
      expect(parseNavigationLocation({hash: `#m=${module}&company=42`})).toEqual({module, companyId: '42'});
    }
    for (const module of ['notifications', 'companies', 'health']) {
      expect(createNavigationState(detail, {module, companyId: 42}).companyId).toBeUndefined();
    }
  });

  it('preserves risk subroutes only within risk and tolerates foreign history state', () => {
    const state = {riskTab: 'detail', riskDetailId: 42, other: 'keep'};
    expect(createNavigationState(state, {module: 'risk', index: 4})).toMatchObject(state);
    expect(createNavigationState(state, {module: 'capa'})).not.toHaveProperty('riskDetailId');
    expect(navigationIndex(null)).toBeNull();
    expect(nextNavigationIndex(null, {replace: true})).toBe(0);
    expect(navigationIndex({[NAVIGATION_STATE_KEY]: true, navigationIndex: -1})).toBeNull();
    expect(createNavigationState([], {module: 'risk'}).navigationIndex).toBe(0);
  });

  it('preserves legacy parsing and hash precedence without swallowing unrelated params', () => {
    expect(parseNavigationLocation({hash: '#/risk?risk_tab=detail'})).toEqual({module: 'risk', companyId: ''});
    expect(parseNavigationLocation({hash: '#m=risk&risk_tab=detail&risk_detail=9', search: '?m=capa&company_id=42'})).toEqual({module: 'risk', companyId: ''});
    expect(parseNavigationLocation({search: '?m=capa&company=42'})).toEqual({module: 'capa', companyId: '42'});
    expect(parseNavigationLocation({hash: '#/%zz'})).toEqual({module: '', companyId: ''});
  });

  it.each([0, '0', null, undefined, '', ' ', '-1', 1.5, '1.5', '1e2', '0x2a', 'null', 'undefined', 'NaN', true, {}, Number.MAX_SAFE_INTEGER + 1])('rejects invalid company ID %j', (id) => {
    expect(normalizeCompanyId(id)).toBe('');
  });

  it.each([42, '42', ' 42 ', '00042'])('normalizes valid company ID %j', (id) => {
    expect(normalizeCompanyId(id)).toBe('42');
  });

  it('allows only the existing OSGB read-only company route, including its empty picker', () => {
    const user = {role: 'company_admin', osgb_id: 4};
    expect(canOpenCompanyCapa(user, 'capa', 42)).toBe(true);
    expect(canOpenCompanyCapa(user, 'capa', '')).toBe(true);
    expect(canOpenCompanyCapa(user, 'risk', 42)).toBe(false);
    expect(canOpenCompanyCapa(user, 'capa', 'bad')).toBe(false);
    expect(canOpenCompanyCapa({...user, company_id: 42}, 'capa', 42)).toBe(false);
    expect(canOpenCompanyCapa({role: 'read_only'}, 'capa', 42)).toBe(false);
  });
});
