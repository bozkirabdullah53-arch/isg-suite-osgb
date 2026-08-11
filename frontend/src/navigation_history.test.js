import {describe, expect, it} from 'vitest';
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

  it('keeps customer context only for the customer detail route', () => {
    const detail = createNavigationState(null, {
      module: 'customer_360',
      companyId: 42,
      index: 2,
    });
    expect(detail.companyId).toBe('42');
    expect(createNavigationState(detail, {module: 'risk', index: 3}).companyId).toBeUndefined();
  });
});

