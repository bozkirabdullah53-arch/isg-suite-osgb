export const NAVIGATION_STATE_KEY = '__isg_suite_navigation_v1';

function objectState(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

/**
 * URL'deki eski (#/risk), mevcut (#m=risk) ve query (?m=risk) biçimlerini
 * tek bir navigasyon kaydına çevirir. Eski bağlantılar böylece bozulmaz.
 */
export function parseNavigationLocation(locationLike = {}) {
  const hash = String(locationLike.hash || '').replace(/^#/, '');
  const search = String(locationLike.search || '');
  try {
    if (hash.startsWith('m=')) {
      const params = new URLSearchParams(hash);
      return {
        module: params.get('m') || '',
        companyId: params.get('company') || '',
      };
    }
    if (hash.startsWith('/')) {
      return {
        module: decodeURIComponent(hash.slice(1).split(/[?#&]/)[0] || ''),
        companyId: '',
      };
    }
    const params = new URLSearchParams(search);
    return {
      module: params.get('m') || '',
      companyId: params.get('company') || params.get('company_id') || '',
    };
  } catch (_) {
    return {module: '', companyId: ''};
  }
}

export function navigationIndex(state) {
  if (state?.[NAVIGATION_STATE_KEY] !== true) return null;
  const index = Number(state.navigationIndex);
  return Number.isInteger(index) && index >= 0 ? index : null;
}

export function nextNavigationIndex(state, {replace = false} = {}) {
  const current = navigationIndex(state);
  if (replace) return current ?? 0;
  return current == null ? 0 : current + 1;
}

export function createNavigationState(
  currentState,
  {module = '', companyId = '', index = 0} = {},
) {
  const next = {
    ...objectState(currentState),
    [NAVIGATION_STATE_KEY]: true,
    module: module || '',
    navigationIndex: Number.isInteger(index) && index >= 0 ? index : 0,
  };
  if (module === 'customer_360' && String(companyId || '').trim()) {
    next.companyId = String(companyId);
  } else {
    delete next.companyId;
  }
  if (module !== 'risk') {
    delete next.riskTab;
    delete next.riskDetailId;
  }
  return next;
}
