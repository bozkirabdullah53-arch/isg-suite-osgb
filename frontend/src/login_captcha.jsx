import React, {useEffect, useRef} from 'react';

let scriptReady;
function loadTurnstile() {
  if (window.turnstile) return new Promise(resolve => window.turnstile.ready(resolve));
  if (scriptReady) return scriptReady;
  scriptReady = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    const timer = setTimeout(() => fail(), 15000);
    function fail() {
      clearTimeout(timer);
      script.remove();
      scriptReady = null;
      reject(new Error('Güvenlik doğrulaması yüklenemedi. Yeniden deneyin.'));
    }
    script.onerror = fail;
    script.onload = () => {
      clearTimeout(timer);
      if (!window.turnstile) {fail(); return;}
      window.turnstile.ready(resolve);
    };
    document.head.append(script);
  });
  return scriptReady;
}

export function LoginCaptcha({siteKey, resetKey = 0, onToken, onError}) {
  const host = useRef(null);
  const handlers = useRef({onToken, onError});
  handlers.current = {onToken, onError};
  useEffect(() => {
    let disposed = false;
    let widget;
    const clear = () => {if (!disposed) handlers.current.onToken?.('');};
    clear();
    loadTurnstile().then(() => {
      if (disposed) return;
      widget = window.turnstile.render(host.current, {
        sitekey: siteKey,
        action: 'login',
        language: 'tr',
        callback: token => {if (!disposed) handlers.current.onToken?.(token);},
        'expired-callback': clear,
        'timeout-callback': clear,
        'error-callback': () => {
          clear();
          if (!disposed) handlers.current.onError?.('Güvenlik doğrulaması tamamlanamadı. Yeniden deneyin.');
        },
      });
    }).catch(error => {if (!disposed) handlers.current.onError?.(error.message);});
    return () => {
      disposed = true;
      if (widget !== undefined && window.turnstile) window.turnstile.remove(widget);
    };
  }, [siteKey, resetKey]);
  return <div ref={host} aria-label="Güvenlik doğrulaması"/>;
}
