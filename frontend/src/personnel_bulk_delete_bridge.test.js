import {afterEach, describe, expect, it, vi} from 'vitest';

let disposeBridge;

afterEach(() => {
  disposeBridge?.();
  disposeBridge = undefined;
  vi.resetModules();
  document.body.innerHTML = '';
  window.location.hash = '';
});

describe('personnel bulk toolbar', () => {
  it('does not count the empty-state row as an employee', async () => {
    window.location.hash = '#m=employees';
    document.body.innerHTML = `
      <button>Seçilenleri Kalıcı Sil (0)</button>
      <table>
        <thead><tr><th>Ad Soyad</th><th>Durum</th><th>İşlem</th></tr></thead>
        <tbody><tr><td colspan="3" class="empty">Kayıt bulunamadı.</td></tr></tbody>
      </table>
    `;

    ({disposePersonnelBulkDeleteBridge: disposeBridge} = await import('./personnel_bulk_delete_bridge'));
    await new Promise((resolve) => setTimeout(resolve, 120));

    expect(document.querySelector('[data-personnel-visible-count]')?.textContent).toBe('0 kayıt gösteriliyor');
    expect(document.querySelector('tbody tr')?.hidden).toBe(false);
  });
});
