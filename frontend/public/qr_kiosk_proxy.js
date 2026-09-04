/*
 * QR kiosk compatibility shim.
 * The kiosk UI historically renders QR images with api.qrserver.com URLs.
 * Keep the existing React component unchanged, but redirect only those QR
 * image URLs to our own API before the browser starts the image request.
 */
(() => {
  const QR_SERVER_HOST = 'api.qrserver.com';
  const QR_API_ORIGIN = window.location.origin;

  function rewriteQrUrl(value) {
    const raw = String(value ?? '');
    if (!raw) return raw;
    try {
      const url = new URL(raw, window.location.href);
      if (url.hostname.toLowerCase() !== QR_SERVER_HOST) return raw;
      if (!/^\/v1\/create-qr-code\/?$/i.test(url.pathname)) return raw;

      const data = url.searchParams.get('data');
      if (!data) return raw;

      const target = new URL('/api/v1/companies/qr-render', QR_API_ORIGIN);
      target.searchParams.set('data', data);
      return target.toString();
    } catch {
      return raw;
    }
  }

  try {
    const proto = HTMLImageElement.prototype;
    const srcDescriptor = Object.getOwnPropertyDescriptor(proto, 'src');

    if (srcDescriptor?.get && srcDescriptor?.set) {
      Object.defineProperty(proto, 'src', {
        configurable: srcDescriptor.configurable,
        enumerable: srcDescriptor.enumerable,
        get() {
          return srcDescriptor.get.call(this);
        },
        set(value) {
          srcDescriptor.set.call(this, rewriteQrUrl(value));
        },
      });
    }

    const originalSetAttribute = proto.setAttribute;
    proto.setAttribute = function patchedSetAttribute(name, value) {
      if (String(name).toLowerCase() === 'src') {
        return originalSetAttribute.call(this, name, rewriteQrUrl(value));
      }
      return originalSetAttribute.call(this, name, value);
    };
  } catch {
    // Do not interfere with application boot if the browser exposes a readonly DOM API.
  }
})();
