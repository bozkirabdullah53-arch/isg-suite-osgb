const PANEL_SELECTOR = '.education-output-panel';
const CERTIFICATE_LABEL = 'Sertifika PDF';
const MANAGE_LABEL = 'Katılım ve Sonuçları Yönet';
const boundButtons = new WeakSet();

function findButton(panel, label) {
  return [...panel.querySelectorAll('button')].find((button) =>
    String(button.textContent || '').includes(label),
  );
}

/**
 * The completion bridge used to set the native `disabled` property when a
 * verified training was not finalized. A disabled control emits no click and
 * therefore looked like a broken PDF download. Keep the established download
 * control interactive: in strict-blocked mode the click opens the result
 * workflow; in legacy/rollback/ready mode React's original PDF handler runs.
 */
export function repairCertificateDownloadGuard(root = document) {
  root.querySelectorAll(PANEL_SELECTOR).forEach((panel) => {
    const certificate = findButton(panel, CERTIFICATE_LABEL);
    if (!certificate) return;

    const blocked = certificate.dataset.completionGuard === 'blocked';
    if (!blocked) {
      certificate.removeAttribute('aria-disabled');
      return;
    }

    if (certificate.disabled) certificate.disabled = false;
    certificate.setAttribute('aria-disabled', 'false');
    certificate.title =
      certificate.title ||
      'Belge koşulları eksik. Katılım ve sınav sonuçlarını yönetmek için tıklayın.';

    if (boundButtons.has(certificate)) return;
    boundButtons.add(certificate);

    certificate.addEventListener(
      'click',
      (event) => {
        if (certificate.dataset.completionGuard !== 'blocked') return;
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        const manage = findButton(panel, MANAGE_LABEL);
        if (manage && !manage.disabled) manage.click();
      },
      true,
    );
  });
}

export function installCertificateDownloadGuardHotfix(root = document) {
  repairCertificateDownloadGuard(root);
  const target = root.documentElement || root;
  if (!target || typeof MutationObserver === 'undefined') return null;
  const observer = new MutationObserver(() => repairCertificateDownloadGuard(root));
  observer.observe(target, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['disabled', 'data-completion-guard'],
  });
  return observer;
}

if (typeof document !== 'undefined') {
  installCertificateDownloadGuardHotfix(document);
}
