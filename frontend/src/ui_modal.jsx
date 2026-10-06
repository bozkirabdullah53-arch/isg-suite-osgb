import {useId, useRef} from 'react';
import {createPortal} from 'react-dom';
import {X} from 'lucide-react';
import {useDialogAccessibility} from './dialog_accessibility';

/**
 * Uygulama geneli modal — document.body'ye portal.
 * Sticky header / content animasyonu altında kesilmeyi önler.
 */
export function AppModal({title, close, children, wide = false, className = ''}) {
  const dialogRef = useRef(null);
  const titleId = useId();
  const hasTitle = title != null && title !== '';
  useDialogAccessibility(dialogRef, {close});

  if (typeof document === 'undefined') return null;
  return createPortal(
    <div
      className={`modal-bg${className ? ` ${className}` : ''}`}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && typeof close === 'function') close();
      }}
    >
      <section
        ref={dialogRef}
        className={`modal${wide ? ' modal-wide' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={hasTitle ? titleId : undefined}
        aria-label={hasTitle ? undefined : 'Pencere'}
        tabIndex={-1}
      >
        {title != null && title !== '' ? (
          <header>
            <h3 id={titleId}>{title}</h3>
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
  const overlayRef = useRef(null);
  useDialogAccessibility(overlayRef, {close});

  if (typeof document === 'undefined') return null;
  return createPortal(
    <div
      ref={overlayRef}
      tabIndex={-1}
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
