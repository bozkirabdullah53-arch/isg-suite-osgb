import {useEffect} from 'react';
import {createPortal} from 'react-dom';
import {X} from 'lucide-react';

/**
 * Uygulama geneli modal — document.body'ye portal.
 * Sticky header / content animasyonu altında kesilmeyi önler.
 */
export function AppModal({title, close, children, wide = false, className = ''}) {
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  if (typeof document === 'undefined') return null;
  return createPortal(
    <div
      className={`modal-bg${className ? ` ${className}` : ''}`}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && typeof close === 'function') close();
      }}
    >
      <section
        className={`modal${wide ? ' modal-wide' : ''}`}
        role="dialog"
        aria-modal="true"
      >
        {title != null && title !== '' ? (
          <header>
            <h3>{title}</h3>
            {typeof close === 'function' ? (
              <button className="icon" type="button" onClick={close} aria-label="Kapat">
                <X size={18} />
              </button>
            ) : null}
          </header>
        ) : null}
        {children}
      </section>
    </div>,
    document.body,
  );
}

/** Ham modal-bg sarmalayıcı (özel içerik için) */
export function PortalOverlay({close, children, className = ''}) {
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  if (typeof document === 'undefined') return null;
  return createPortal(
    <div
      className={`modal-bg${className ? ` ${className}` : ''}`}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && typeof close === 'function') close();
      }}
    >
      {children}
    </div>,
    document.body,
  );
}

export default AppModal;
