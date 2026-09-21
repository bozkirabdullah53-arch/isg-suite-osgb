import {useCallback, useEffect, useState} from 'react';
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
    return null;
  }
}

export function PwaShortcutPrompt() {
  const [open, setOpen] = useState(false);
  const [help, setHelp] = useState('');
  const [deferred, setDeferred] = useState(null);
  const [mobile, setMobile] = useState(false);

  useEffect(() => {
    const choice = readShortcutChoice(storage());
    const mobileViewport = isMobileViewport(window);
    setMobile(mobileViewport);
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
    writeShortcutChoice('accepted', storage());
    if (deferred && typeof deferred.prompt === 'function') {
      try {
        deferred.prompt();
        const result = await deferred.userChoice;
        setDeferred(null);
        if (result?.outcome === 'accepted') {
          writeShortcutChoice('installed', storage());
          setOpen(false);
          return;
        }
      } catch (_) {
        // Native prompt can be unavailable; fall through to manual steps.
      }
    }
    setHelp(shortcutInstructionText(isIosDevice(window), mobile));
  }, [deferred, mobile]);

  if (typeof document === 'undefined' || (!open && !help)) return null;

  return createPortal(
    <div className="pwa-shortcut-overlay" role="dialog" aria-modal="true" aria-labelledby="pwa-shortcut-title">
      <div className="pwa-shortcut-card">
        <h2 id="pwa-shortcut-title">İSG Suite</h2>
        <p>
          {help || 'Web sayfasının kısa yolu oluşturulsun mu?'}
        </p>
        <div className="pwa-shortcut-actions">
          {help ? (
            <button type="button" className="pwa-yes" onClick={() => close('accepted')} onPointerUp={() => close('accepted')}>Tamam</button>
          ) : (
            <>
              <button type="button" className="pwa-no" onClick={() => close('dismissed')} onPointerUp={() => close('dismissed')}>Hayır</button>
              <button type="button" className="pwa-yes" onClick={() => void accept()}>Evet</button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
