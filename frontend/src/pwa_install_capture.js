// Capture the Android/Chromium PWA install event before React mounts.
// This must be an external module because the production CSP blocks inline scripts.
(function capturePwaInstallPrompt() {
  if (typeof window === 'undefined') return;
  if (window.__isgPwaInstallCaptureInstalled) return;
  window.__isgPwaInstallCaptureInstalled = true;

  window.addEventListener('beforeinstallprompt', (event) => {
    if (window.matchMedia?.('(display-mode: standalone)')?.matches) return;
    event.preventDefault();
    window.__isgDeferredInstallPrompt = event;
    window.__isgPwaInstallPromptAvailable = true;
  });

  window.addEventListener('appinstalled', () => {
    window.__isgDeferredInstallPrompt = null;
    window.__isgPwaInstallPromptAvailable = false;
  });
})();
