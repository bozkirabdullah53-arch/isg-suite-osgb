import {useLayoutEffect, useRef} from 'react';

const dialogs = [];
let previousOverflow = '';

function focusableElements(root) {
  return Array.from(root.querySelectorAll('a[href], button, input, select, textarea, summary, [tabindex]')).filter((element) => {
    if (element.disabled || (element.tabIndex < 0 && element.tagName !== 'SUMMARY') || element.getAttribute('tabindex') === '-1' || element.matches('input[type="hidden"]')) return false;
    for (let node = element; node && node !== root.parentElement; node = node.parentElement) {
      if (node.hidden || node.inert || node.getAttribute('aria-hidden') === 'true') return false;
      const style = getComputedStyle(node);
      if (style.display === 'none' || style.visibility === 'hidden') return false;
      if (node.tagName === 'DETAILS' && !node.open && !node.querySelector('summary')?.contains(element)) return false;
    }
    return true;
  });
}

/** Shared focus/scroll management; nested dialogs release only their own lock. */
export function useDialogAccessibility(ref, {enabled = true, close} = {}) {
  const closeRef = useRef(close);
  closeRef.current = close;

  useLayoutEffect(() => {
    const root = ref.current;
    if (!enabled || !root) return undefined;
    const previousFocus = document.activeElement;
    const entry = {root};
    if (!dialogs.length) {
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      document.body.setAttribute('data-dialog-open', 'true');
    }
    dialogs.push(entry);
    const topmost = () => dialogs.at(-1) === entry;
    const focusFirst = () => {
      const elements = focusableElements(root);
      const field = elements.find((element) => element.hasAttribute('autofocus')) ||
        elements.find((element) => element.matches('input, select, textarea')) || elements[0] || root;
      field.focus({preventScroll: true});
    };
    const onFocus = (event) => {
      if (topmost() && !root.contains(event.target)) focusFirst();
    };
    const onKeyDown = (event) => {
      if (!topmost()) return;
      if (event.key === 'Escape' && typeof closeRef.current === 'function') {
        event.preventDefault();
        event.stopPropagation();
        closeRef.current();
      } else if (event.key === 'Tab') {
        const elements = focusableElements(root);
        const first = elements[0];
        const last = elements.at(-1);
        if (!first) {
          event.preventDefault();
          root.focus();
        } else if (event.shiftKey && (document.activeElement === first || !root.contains(document.activeElement))) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || !root.contains(document.activeElement))) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKeyDown, true);
    document.addEventListener('focusin', onFocus, true);
    focusFirst();
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      document.removeEventListener('focusin', onFocus, true);
      const wasTopmost = topmost();
      const index = dialogs.indexOf(entry);
      if (index >= 0) dialogs.splice(index, 1);
      if (!dialogs.length) {
        document.body.style.overflow = previousOverflow;
        document.body.removeAttribute('data-dialog-open');
      }
      // Wait until React has also re-enabled or updated the opener.
      queueMicrotask(() => {
        if (wasTopmost && previousFocus?.isConnected && typeof previousFocus.focus === 'function') {
          previousFocus.focus({preventScroll: true});
        }
      });
    };
  }, [enabled, ref]);
}
