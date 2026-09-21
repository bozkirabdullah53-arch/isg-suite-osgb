import {useCallback, useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {
  isIosDevice,
  isMobileViewport,
  isStandaloneDisplay,
  readShortcutChoice,
  shouldAskShortcutPrompt,
  shortcutInstructionText,
  writeShortcutChoice,
} from './pwa_shortcut_prompt_logic';
import './pwa_shortcut_prompt.css';

function storage() {
  try {
    return window.localStorage;
  } catch (_) {
    try {
      return window.sessionStorage;
    } catch (_) {
      return null;
    }
  }
}

export function PwaShortcutPrompt() {
  const [open, setOpen] = useState(false);
  const [help, setHelp] = useState('');
  const [deferred, setDeferred] = useState(null);
  const [mobile, setMobile] = useState(false);

  const [installed, setInstalled] = useState(false);
  const [busy, setBusy] = useState(false);
  const installing = useRef(false);

  useEffect(() => {
    const choice = readShortcutChoice(storage());
    const mobileViewport = isMobileViewport(window);
    setMobile(mobileViewport);
    setInstalled(isStandaloneDisplay(window));
    const ask = shouldAskShortcutPrompt({
      mobile: mobileViewport,
      standalone: isStandaloneDisplay(window),
      choice,
    });
    if (ask) setOpen(true);
    if (window.__isgDeferredInstallPrompt) {
      setDeferred(window.__isgDeferredInstallPrompt);
    }

    const onPrompt = (event) => {
      if (isStandaloneDisplay(window)) return;
      event.preventDefault();
      window.__isgDeferredInstallPrompt = event;
      setDeferred(event);
    };
    const onInstalled = () => {
      writeShortcutChoice('installed', storage());
      window.__isgDeferredInstallPrompt = null;
      setDeferred(null);
      setInstalled(true);
      setOpen(false);
      setHelp('');
    };
    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);

  const close = useCallback((value) => {
    writeShortcutChoice(value, storage());
    setHelp('');
    setOpen(false);
  }, []);

  const accept = useCallback(async () => {
    if (installing.current) return;
    const event = deferred || window.__isgDeferredInstallPrompt;
    if (event && typeof event.prompt === 'function') {
      installing.current = true;
      setBusy(true);
      // Native installation events are single-use, including failed attempts.
      window.__isgDeferredInstallPrompt = null;
      setDeferred(null);
      try {
        await event.prompt();
        const result = await event.userChoice;
        if (result?.outcome === 'accepted') {
          setOpen(false);
          setHelp('');
          return;
        }
      } catch (_) {
        // Keep manual installation available if the browser rejects the prompt.
      } finally {
        installing.current = false;
        setBusy(false);
      }
    }
    setHelp(shortcutInstructionText(isIosDevice(window), mobile));
  }, [deferred, mobile]);

  if (typeof document === 'undefined' || installed) return null;
  if (!open && !help) {
    return mobile ? createPortal(
      <button type="button" className="pwa-shortcut-reopen" onClick={() => setOpen(true)}>
        Ana ekrana ekle
      </button>,
      document.body,
    ) : null;
  }

  return createPortal(
    <div className="pwa-shortcut-overlay" role="dialog" aria-modal="true" aria-labelledby="pwa-shortcut-title">
      <div className="pwa-shortcut-card">
        <h2 id="pwa-shortcut-title">İSG Suite</h2>
        <p>
          {help || 'Web sayfasının kısa yolu oluşturulsun mu?'}
        </p>
        <div className="pwa-shortcut-actions">
          {help ? (
            <button type="button" className="pwa-yes" onClick={() => close('dismissed')}>Tamam</button>
          ) : (
            <>
              <button type="button" className="pwa-no" onClick={() => close('dismissed')}>Hayır</button>
              <button type="button" className="pwa-yes" disabled={busy} onClick={() => void accept()}>Evet</button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
