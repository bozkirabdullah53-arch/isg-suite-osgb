const STYLE_ID = 'password-visibility-bridge-style';
const ENHANCED_ATTR = 'data-password-visibility-enhanced';

const eyeIcon = (visible) => visible
  ? '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M2.2 12s3.6-6 9.8-6 9.8 6 9.8 6-3.6 6-9.8 6-9.8-6-9.8-6Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="12" r="2.7" fill="none" stroke="currentColor" stroke-width="2"/></svg>'
  : '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M3 3l18 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M10.6 6.2A10.9 10.9 0 0 1 12 6c6.2 0 9.8 6 9.8 6a16.8 16.8 0 0 1-3.1 3.7M6.1 6.1C3.6 8 2.2 12 2.2 12s3.6 6 9.8 6c1.5 0 2.8-.3 4-.8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';

function ensureStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    .password-visibility-field { position: relative; }
    .password-visibility-field .password-visibility-input { padding-right: 48px !important; }
    .password-visibility-toggle {
      position: absolute;
      right: 9px;
      bottom: 7px;
      width: 36px;
      height: 36px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      margin: 0;
      border: 0;
      border-radius: 10px;
      background: transparent;
      color: #0f766e;
      cursor: pointer;
      box-shadow: none;
      z-index: 2;
    }
    .password-visibility-toggle:hover { background: rgba(13, 148, 136, 0.10); }
    .password-visibility-toggle:focus-visible {
      outline: 2px solid #14b8a6;
      outline-offset: 2px;
    }
    .password-visibility-toggle svg { pointer-events: none; }
  `;
  document.head.appendChild(style);
}

function setToggleState(input, button) {
  const visible = input.type === 'text';
  button.innerHTML = eyeIcon(visible);
  button.setAttribute('aria-pressed', visible ? 'true' : 'false');
  button.setAttribute('aria-label', visible ? 'Şifreyi gizle' : 'Şifreyi göster');
  button.title = visible ? 'Şifreyi gizle' : 'Şifreyi göster';
}

function enhancePasswordInput(input) {
  if (!(input instanceof HTMLInputElement)) return;
  if (input.getAttribute(ENHANCED_ATTR) === 'true') return;
  if (input.type !== 'password') return;

  const field = input.closest('label.field');
  if (!field || !field.closest('.login-shell--apply')) return;

  ensureStyles();
  input.setAttribute(ENHANCED_ATTR, 'true');
  input.classList.add('password-visibility-input');
  field.classList.add('password-visibility-field');

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'password-visibility-toggle';
  setToggleState(input, button);

  button.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    input.type = input.type === 'password' ? 'text' : 'password';
    setToggleState(input, button);
    input.focus({ preventScroll: true });
  });

  field.appendChild(button);
}

function scan(root = document) {
  if (root instanceof HTMLInputElement) enhancePasswordInput(root);
  if (!(root instanceof Element || root instanceof Document || root instanceof DocumentFragment)) return;
  root.querySelectorAll?.('.login-shell--apply input[type="password"]').forEach(enhancePasswordInput);
}

scan();

const observer = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    for (const node of mutation.addedNodes) {
      if (node instanceof Element) scan(node);
    }
  }
});

observer.observe(document.documentElement, { childList: true, subtree: true });
