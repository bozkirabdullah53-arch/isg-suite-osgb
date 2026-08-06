import {
  beginCsgbPrint,
  endCsgbPrint,
  isCsgbAuditPage,
  isCsgbPrintButton,
} from './csgb_audit_print_logic';
import './csgb_audit_print.css';

let cleanupTimer = null;

function scheduleFallbackCleanup() {
  window.clearTimeout(cleanupTimer);
  // afterprint is the normal cleanup path. The long fallback only protects
  // against browsers that never emit afterprint after a cancelled dialog.
  cleanupTimer = window.setTimeout(() => endCsgbPrint(document), 300_000);
}

// Capture runs before React's existing onClick and prepares the DOM before
// the component calls window.print(). The existing working button is retained.
document.addEventListener('click', (event) => {
  if (!isCsgbPrintButton(event.target)) return;
  if (beginCsgbPrint(document)) scheduleFallbackCleanup();
}, true);

// Keyboard/browser-menu printing receives the same safe layout.
window.addEventListener('beforeprint', () => {
  if (isCsgbAuditPage(document) && beginCsgbPrint(document)) {
    scheduleFallbackCleanup();
  }
});

window.addEventListener('afterprint', () => {
  window.clearTimeout(cleanupTimer);
  endCsgbPrint(document);
});
