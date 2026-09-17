import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {api, downloadFile} from './api';
import {EmployeeSelfServicePage} from './employee_self_service';

vi.mock('./api', () => ({api: vi.fn(), downloadFile: vi.fn()}));

const ready = {
  id: 'classroom-7', kind: 'classroom', source_id: 7, title: 'İlk Yardım',
  certificate_number: 'EGT-7', downloadable: true,
  download_path: '/self-service/certificates/classroom/7.pdf',
};
const pending = {
  id: 'remote-9', kind: 'remote', source_id: 9, title: 'Hijyen Eğitimi',
  downloadable: false, download_path: null, block_reason: 'Final sınavı henüz tamamlanmadı.',
};

describe('employee participation documents', () => {
  let container;
  let root;
  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    vi.resetAllMocks();
    container = document.createElement('div');
    document.body.append(container);
    root = createRoot(container);
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  });

  async function render(items = [ready, pending]) {
    api.mockResolvedValueOnce({certificates: {
      total: items.length, downloadable: items.filter((item) => item.downloadable).length, items,
    }});
    await act(async () => root.render(React.createElement(EmployeeSelfServicePage)));
  }

  it('explains pending documents and downloads only the selected personal PDF', async () => {
    await render();
    const section = container.querySelector('.ess-certificates-card');
    expect(section.textContent).toContain('Katılım Belgelerim');
    expect(section.textContent).toContain(pending.block_reason);
    expect(section.querySelectorAll('button')).toHaveLength(1);
    await act(async () => section.querySelector('button').click());
    expect(downloadFile).toHaveBeenCalledExactlyOnceWith(ready.download_path, 'egitim-katilim-belgesi-EGT-7.pdf');
  });

  it('filters ready and pending records without a second data request', async () => {
    await render();
    const select = container.querySelector('.ess-certificates-card select');
    await act(async () => {
      select.value = 'pending';
      select.dispatchEvent(new Event('change', {bubbles: true}));
    });
    const section = container.querySelector('.ess-certificates-card');
    expect(section.textContent).toContain(pending.title);
    expect(section.textContent).not.toContain(ready.title);
    expect(section.querySelector('button')).toBeNull();
    expect(api).toHaveBeenCalledTimes(1);
  });

  it('shows a denied download and leaves the list usable for retry', async () => {
    downloadFile.mockRejectedValueOnce(new Error('Katılımınız doğrulanmadı.'));
    await render();
    await act(async () => container.querySelector('.ess-certificates-card button').click());
    expect(container.textContent).toContain('Katılımınız doğrulanmadı.');
    expect(container.querySelector('.ess-certificates-card button').disabled).toBe(false);
  });

  it('refreshes the list after a training becomes eligible', async () => {
    await render([pending]);
    api.mockResolvedValueOnce({certificates: {total: 1, downloadable: 1, items: [ready]}});
    await act(async () => container.querySelector('.ess-header button').click());
    expect(container.querySelector('.ess-certificates-card').textContent).toContain(ready.title);
    expect(container.querySelector('.ess-certificates-card button')).not.toBeNull();
  });

  it('renders a useful empty state', async () => {
    await render([]);
    expect(container.textContent).toContain('Henüz katılım belgeniz yok.');
  });
});
