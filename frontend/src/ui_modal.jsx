import {useEffect} from 'react';
import {createPortal} from 'react-dom';
import {X} from 'lucide-react';

function lockModalBody() {
  if (typeof document === 'undefined' || !document.body) return () => {};

  const body = document.body;
  const openCount = Number(body.dataset.modalOpenCount || 0);
  if (openCount === 0) {
    body.dataset.modalPreviousOverflow = body.style.overflow;
  }

  body.dataset.modalOpenCount = String(openCount + 1);
  body.classList.add('modal-open');
  body.style.overflow = 'hidden';

  return () => {
    const currentCount = Math.max(0, Number(body.dataset.modalOpenCount || 1) - 1);
    if (currentCount === 0) {
      body.style.overflow = body.dataset.modalPreviousOverflow || '';
      delete body.dataset.modalOpenCount;
      delete body.dataset.modalPreviousOverflow;
      body.classList.remove('modal-open');
    } else {
      body.dataset.modalOpenCount = String(currentCount);
    }
  };
}

/**
 * Uygulama geneli modal — document.body'ye portal.
 * Sticky header / content animasyonu altında kesilmeyi önler.
 */
export function AppModal({title, close, children, wide = false, className = ''}) {
  useEffect(() => lockModalBody(), []);

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
  useEffect(() => lockModalBody(), []);

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
