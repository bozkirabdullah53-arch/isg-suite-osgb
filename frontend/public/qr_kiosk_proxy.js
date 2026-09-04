/* QR kiosk compatibility shim. Intercept only legacy QR-server image URLs and fetch the PNG through the authenticated API session. */
(() => {
  const QR_SERVER_HOST = 'api.qrserver.com';
  const API_QR_PATH = '/api/v1/companies/qr-render';

  function token() {
    try { return (sessionStorage.getItem('isg_token') || localStorage.getItem('isg_token') || '').trim(); }
    catch { return ''; }
  }

  function isLegacy(value) {
    try {
      const u = new URL(String(value ?? ''), window.location.href);
      return u.hostname.toLowerCase() === QR_SERVER_HOST && /^\/v1\/create-qr-code\/?$/i.test(u.pathname) && !!u.searchParams.get('data');
    } catch { return false; }
  }

  async function loadQr(value, img) {
    const source = new URL(String(value), window.location.href);
    const data = source.searchParams.get('data');
    if (!data) return;
    const endpoint = new URL(API_QR_PATH, window.location.origin);
    endpoint.searchParams.set('data', data);
    const headers = {};
    const bearer = token();
    if (bearer) headers.Authorization = `Bearer ${bearer}`;
    try {
      const response = await fetch(endpoint.toString(), { method: 'GET', credentials: 'include', headers, cache: 'no-store' });
      if (!response.ok) throw new Error(`QR renderer HTTP ${response.status}`);
      const blob = await response.blob();
      if (!blob.type.toLowerCase().startsWith('image/')) throw new Error(`QR renderer content-type ${blob.type || 'unknown'}`);
      const objectUrl = URL.createObjectURL(blob);
      const setter = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src')?.set;
      if (setter) setter.call(img, objectUrl); else img.setAttribute('src', objectUrl);
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    } catch (error) {
      try { img.dataset.qrLoadError = String(error?.message || error || 'unknown'); } catch { /* ignore */ }
    }
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
            if (!handled.has(this)) { handled.add(this); void loadQr(value, this); }
            return;
          }
          descriptor.set.call(this, value);
        },
      });
    }
    const originalSetAttribute = proto.setAttribute;
    proto.setAttribute = function(name, value) {
      if (String(name).toLowerCase() === 'src' && isLegacy(value)) {
        if (!handled.has(this)) { handled.add(this); void loadQr(value, this); }
        return;
      }
      return originalSetAttribute.call(this, name, value);
    };
  } catch {
    /* Never block application boot. */
  }
})();