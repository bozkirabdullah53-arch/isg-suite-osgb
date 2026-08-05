/** @vitest-environment happy-dom */

import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {api} from './api';
import {OhsCommitteePage} from './ohs_committee_page';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

vi.mock('./api', () => ({
  api: vi.fn(),
  downloadFile: vi.fn(),
}));

vi.mock('./committee_approval_queue', () => ({
  CommitteeApprovalQueue: () => null,
}));

const member = {
  id: 41,
  company_id: 1,
  full_name: 'Tarihsel Kurul Üyesi',
  initials: 'TK',
  role_code: 'calisan_temsilcisi',
  role_label: 'Çalışan Temsilcisi',
  job_title_snapshot: 'Operatör',
  is_mandatory: false,
  identity_key: 'employee:1:41',
};

function setupApi({removeError = null, pendingRemoval = null} = {}) {
  api.mockImplementation((path, options = {}) => {
    if (path === '/companies') return Promise.resolve([{id: 1, name: 'AYAN ACADEMY'}]);
    if (path === '/ohs-committee/meta') return Promise.resolve({
      roles: [{code: 'calisan_temsilcisi', label: 'Çalışan Temsilcisi'}],
    });
    if (path.startsWith('/ohs-committee/candidates?')) return Promise.resolve({
      mandatory: [],
      other: [],
      missing_mandatory: [],
    });
    if (path.startsWith('/ohs-committee/members/detail?')) return Promise.resolve([member]);
    if (path.startsWith('/ohs-committee/meetings?')) return Promise.resolve([]);
    if (path === `/ohs-committee/members/${member.id}/remove` && options.method === 'POST') {
      if (pendingRemoval) return pendingRemoval;
      if (removeError) return Promise.reject(removeError);
      return Promise.resolve({ok: true, message: 'Kurul üyesi başarıyla çıkarıldı.'});
    }
    return Promise.resolve([]);
  });
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe('OhsCommitteePage member removal', () => {
  let container;
  let root;

  beforeEach(() => {
    api.mockReset();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  async function renderPage() {
    await act(async () => {
      root.render(<OhsCommitteePage user={{id: 7, role: 'global_admin', company_id: 1}} />);
    });
    await flush();
  }

  function buttonByText(text) {
    return [...document.querySelectorAll('button')].find((button) => button.textContent.includes(text));
  }

  it('opens a professional confirmation dialog and cancel does not call backend', async () => {
    setupApi();
    await renderPage();

    expect(container.textContent).toContain('Tarihsel Kurul Üyesi');
    await act(async () => buttonByText('Kuruldan Çıkar').click());

    expect(document.body.textContent).toContain('Kurul Üyeliğini Sonlandır');
    expect(document.body.textContent).toContain('Tarihsel toplantı, katılım, onay, PDF ve elektronik imza kayıtları silinmez.');
    expect(document.body.textContent).toContain('Çalışan Temsilcisi');

    await act(async () => buttonByText('Vazgeç').click());

    expect(api).not.toHaveBeenCalledWith(
      `/ohs-committee/members/${member.id}/remove`,
      expect.anything(),
    );
    expect(container.textContent).toContain('Tarihsel Kurul Üyesi');
  });

  it('double confirmation creates only one in-flight removal request', async () => {
    let resolveRemoval;
    const pendingRemoval = new Promise((resolve) => { resolveRemoval = resolve; });
    setupApi({pendingRemoval});
    await renderPage();
    await act(async () => buttonByText('Kuruldan Çıkar').click());

    const confirm = buttonByText('Üyeliği Sonlandır');
    await act(async () => {
      confirm.click();
      confirm.click();
      await Promise.resolve();
    });

    const removalCalls = api.mock.calls.filter(([path]) => path === `/ohs-committee/members/${member.id}/remove`);
    expect(removalCalls).toHaveLength(1);

    resolveRemoval({ok: true, message: 'Kurul üyesi başarıyla çıkarıldı.'});
    await flush();
  });

  it('keeps member and dialog state when backend removal fails', async () => {
    setupApi({removeError: new Error('Aktif onay akışı nedeniyle üyelik sonlandırılamaz.')});
    await renderPage();
    await act(async () => buttonByText('Kuruldan Çıkar').click());
    await act(async () => buttonByText('Üyeliği Sonlandır').click());
    await flush();

    expect(document.body.textContent).toContain('Aktif onay akışı nedeniyle üyelik sonlandırılamaz.');
    expect(document.body.textContent).toContain('Kurul Üyeliğini Sonlandır');
    expect(container.textContent).toContain('Tarihsel Kurul Üyesi');
  });
});
