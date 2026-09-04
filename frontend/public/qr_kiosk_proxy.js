/* QR kiosk compatibility shim. Only rewrite workplace QR image URLs; leave all other app images untouched. */
(() => {
  const QR_SERVER_HOST = 'api.qrserver.com';
  const QR_API_ORIGIN = 'https://isg-suite-api-1u9t.onrender.com';
  const API_QR_PATH = '/api/v1/companies/qr-render';

  function workplaceQrUrl(value) {
    try {
      const u = new URL(String(value ?? ''), window.location.href);
      if (
        u.hostname.toLowerCase() !== QR_SERVER_HOST
        || !/^\/v1\/create-qr-code\/?$/i.test(u.pathname)
      ) return null;
      const data = u.searchParams.get('data') || '';
      if (!/^ISGSUITE:WP(?:TEMP)?:/i.test(data)) return null;
      const endpoint = new URL(API_QR_PATH, QR_API_ORIGIN);
      endpoint.searchParams.set('data', data);
      return endpoint.toString();
    } catch {
      return null;
    }
  }

  function rewriteImage(img) {
    try {
      const current = img?.getAttribute('src');
      const replacement = workplaceQrUrl(current);
      if (!replacement || current === replacement) return;
      img.setAttribute('src', replacement);
    } catch {
      /* Never block application boot. */
    }
  }

  function scan(root) {
    try {
      if (root instanceof HTMLImageElement) rewriteImage(root);
      const images = root?.querySelectorAll?.('img[src]') || [];
      images.forEach(rewriteImage);
    } catch {
      /* ignore */
    }
  }

  try {
    scan(document);
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === 'attributes' && mutation.target instanceof HTMLImageElement) {
          rewriteImage(mutation.target);
          continue;
        }
        for (const node of mutation.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) scan(node);
        }
      }
    });
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['src'],
    });
  } catch {
    /* Never block application boot. */
  }
})();
