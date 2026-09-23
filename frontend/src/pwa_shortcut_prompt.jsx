import {useCallback, useEffect, useState} from 'react';
import {createPortal} from 'react-dom';
import {
  isAutomatedSession,
  isIosDevice,
  isMobileViewport,
  isStandaloneDisplay,
  readShortcutEntry,
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
  const [pending, setPending] = useState(false);
  const [help, setHelp] = useState('');
  const [deferred, setDeferred] = useState(null);
  const [mobile, setMobile] = useState(false);

  useEffect(() => {
    const entry = readShortcutEntry(storage());
    const mobileViewport = isMobileViewport(window);
    setMobile(mobileViewport);
    const ask = shouldAskShortcutPrompt({
      mobile: mobileViewport,
      standalone: isStandaloneDisplay(window),
      automated: isAutomatedSession(window),
      choice: entry.choice,
      choiceTime: entry.time,
      now: Date.now(),
    });
    setPending(ask);
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
      setPending(false);
      setHelp('');
    };
    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);

  /**
   * Kısayol istemini kullanıcı etkileşimine bağlamak yerine, uygulama ilk
   * boyamadan sonra kısa bir gecikmeyle açıyoruz. Böylece kullanıcı ilk
   * dokunuşu yapmak zorunda kalmaz ve istem belirgin biçimde daha hızlı görünür.
   * Otomasyon oturumları shouldAskShortcutPrompt tarafından zaten engellenir.
   */
  useEffect(() => {
    if (!pending || open) return undefined;
    const timer = window.setTimeout(() => setOpen(true), 350);
    return () => window.clearTimeout(timer);
  }, [open, pending]);

  const close = useCallback((value) => {
    writeShortcutChoice(value, storage());
    setHelp('');
    setOpen(false);
    setPending(false);
  }, []);

  const accept = useCallback(async () => {
    writeShortcutChoice('accepted', storage());

    // iOS, ana ekrana ekleme işlemini web sayfasının JavaScript'ine açmaz.
    // Android'deki beforeinstallprompt akışını iPhone'da zorlamıyoruz.
    if (isIosDevice(window)) {
      setHelp(shortcutInstructionText(true, mobile));
      return;
    }

    if (deferred && typeof deferred.prompt === 'function') {
      try {
        deferred.prompt();
        const result = await deferred.userChoice;
        setDeferred(null);
        if (result?.outcome === 'accepted') {
          writeShortcutChoice('installed', storage());
          setOpen(false);
          setPending(false);
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
        <p className="pwa-shortcut-message">
          {help || 'Web sayfasının kısa yolu oluşturulsun mu?'}
        </p>
        <div className="pwa-shortcut-actions">
          {help ? (
            <button type="button" className="pwa-yes" onClick={() => close('accepted')} onPointerUp={() => close('accepted')}>Tamam</button>
          ) : (
            <>
              <button type="button" className="pwa-no" onClick={() => close('dismissed')} onPointerUp={() => close('dismissed')}>Hayır</button>
              <button type="button" className="pwa-yes" onClick={() => void accept()}>
                {isIosDevice(window) ? 'Kurulum adımlarını göster' : 'Evet'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
