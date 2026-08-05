import {afterEach, describe, expect, it, vi} from 'vitest';
import {repairCertificateDownloadGuard} from './training_certificate_download_hotfix';

afterEach(() => {
  document.body.innerHTML = '';
});

describe('certificate download guard hotfix', () => {
  it('keeps the control clickable and opens result management when strict-blocked', () => {
    document.body.innerHTML = `
      <section class="education-output-panel">
        <button id="certificate" disabled data-completion-guard="blocked">
          Sertifika PDF (Katılım Belgeleri)
        </button>
        <button id="manage">Katılım ve Sonuçları Yönet</button>
      </section>`;

    const certificate = document.getElementById('certificate');
    const manage = document.getElementById('manage');
    const downloadHandler = vi.fn();
    const manageHandler = vi.fn();
    certificate.addEventListener('click', downloadHandler);
    manage.addEventListener('click', manageHandler);

    repairCertificateDownloadGuard(document);

    expect(certificate.disabled).toBe(false);
    certificate.click();
    expect(manageHandler).toHaveBeenCalledTimes(1);
    expect(downloadHandler).not.toHaveBeenCalled();
  });

  it('does not intercept legacy, rollback or ready downloads', () => {
    document.body.innerHTML = `
      <section class="education-output-panel">
        <button id="certificate" data-completion-guard="ready">
          Sertifika PDF (Katılım Belgeleri)
        </button>
        <button id="manage">Katılım ve Sonuçları Yönet</button>
      </section>`;

    const certificate = document.getElementById('certificate');
    const downloadHandler = vi.fn();
    certificate.addEventListener('click', downloadHandler);

    repairCertificateDownloadGuard(document);
    certificate.click();

    expect(downloadHandler).toHaveBeenCalledTimes(1);
  });
});
