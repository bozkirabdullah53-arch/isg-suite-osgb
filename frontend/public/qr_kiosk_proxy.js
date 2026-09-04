/* QR kiosk compatibility shim. Fetch QR PNG with the current auth session.
 * If the kiosk access token is missing/expired, refresh the existing cookie session once. */
(() => {
  const QR_SERVER_HOST = 'api.qrserver.com';
  const API_QR_PATH = '/api/v1/companies/qr-render';
  const REFRESH_PATH = '/api/v1/auth/refresh';

  function readToken() {
    try {
      return (sessionStorage.getItem('isg_token') || localStorage.getItem('isg_token') || '').trim();
    } catch {
      return '';
    }
  }

  function rememberToken(value) {
    const token = String(value || '').trim();
    if (!token) return;
    try {
      sessionStorage.setItem('isg_token', token);
      localStorage.removeItem('isg_token');
    } catch {
      // Never block the kiosk if storage is unavailable.
    }
  }

  async function refreshToken() {
    try {
      const response = await fetch(REFRESH_PATH, {
        method: 'POST',
        credentials: 'include',
        cache: 'no-store',
      });
      if (!response.ok) return '';
      const body = await response.json().catch(() => ({}));
      const token = String(body?.access_token || '').trim();
      if (token) rememberToken(token);
      return token;
    } catch {
      return '';
    }
  }

  function isLegacy(value) {
    try {
      const u = new URL(String(value ?? ''), window.location.href);
      return u.hostname.toLowerCase() === QR_SERVER_HOST
        && /^\/v1\/create-qr-code\/?$/i.test(u.pathname)
        && !!u.searchParams.get('data');
    } catch {
      return false;
    }
  }

  async function fetchQr(endpoint, bearer) {
    const headers = bearer ? { Authorization: `Bearer ${bearer}` } : {};
    return fetch(endpoint.toString(), {
      method: 'GET',
      credentials: 'include',
      headers,
      cache: 'no-store',
    });
  }

  async function loadQr(value, img) {
    const source = new URL(String(value), window.location.href);
    const data = source.searchParams.get('data');
    if (!data) return;

    const endpoint = new URL(API_QR_PATH, window.location.origin);
    endpoint.searchParams.set('data', data);

    let bearer = readToken();
    let response = await fetchQr(endpoint, bearer);

    if (response.status === 401) {
      const refreshed = await refreshToken();
      if (refreshed) {
        bearer = refreshed;
        response = await fetchQr(endpoint, bearer);
      }
    }

    if (!response.ok) {
      try { img.dataset.qrLoadError = `QR renderer HTTP ${response.status}`; } catch { /* ignore */ }
      return;
    }

    const blob = await response.blob();
    if (!blob.type.toLowerCase().startsWith('image/')) {
      try { img.dataset.qrLoadError = `QR renderer content-type ${blob.type || 'unknown'}`; } catch { /* ignore */ }
      return;
    }

    const objectUrl = URL.createObjectURL(blob);
    const setter = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src')?.set;
    if (setter) setter.call(img, objectUrl);
    else img.setAttribute('src', objectUrl);
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
  }

  try {
    const proto = HTMLImageElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, 'src');
    const handled = new WeakSet();

    if (descriptor?.get && descriptor?.set) {
      Object.defineProperty(proto, 'src', {
        configurable: descriptor.configurable,
        enumerable: descriptor.enumerable,
        get() { return descriptor.get.call(this); },
        set(value) {
          if (isLegacy(value)) {
            if (!handled.has(this)) {
              handled.add(this);
              void loadQr(value, this);
            }
            return;
          }
          descriptor.set.call(this, value);
        },
      });
    }

    const originalSetAttribute = proto.setAttribute;
    proto.setAttribute = function(name, value) {
      if (String(name).toLowerCase() === 'src' && isLegacy(value)) {
        if (!handled.has(this)) {
          handled.add(this);
          void loadQr(value, this);
        }
        return;
      }
      return originalSetAttribute.call(this, name, value);
    };
  } catch {
    /* Never block application boot. */
  }
})();
