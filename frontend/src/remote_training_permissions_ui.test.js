import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {api} from './api';
import {RemoteBasicOhsTrainingPanel} from './remote_basic_ohs_training_core.jsx';

vi.mock('./api', () => ({
  api: vi.fn(), API_URL: '/api/v1', downloadFile: vi.fn(), uploadFile: vi.fn(),
}));

let root;
let host;

beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.resetAllMocks();
});

async function renderRole(role, {editFlag = role === 'global_admin'} = {}) {
  const packageRow = {
    id: 10, code: 'common-basic-ohs', title: 'Merkezi Ortak Eğitim', is_shared: true,
    status: role === 'global_admin' ? 'unpublished' : 'published',
    automatic_exam_ready: true, automatic_exam_question_count: 20,
    sections: [{id: 20, code: 'GEN-01', title: 'Ortak Ders', status: 'active', videos: [{
      id: 30, title: 'Eğitim Videosu', status: role === 'global_admin' ? 'ready_for_review' : 'published',
      is_current: true, order_index: 1,
    }]}],
  };
  api.mockImplementation(async (path) => {
    if (path === '/trainings/remote/meta') return {
      enabled: true, can_manage: role !== 'read_only', can_operate: role !== 'read_only',
      can_edit_content: editFlag, can_edit_shared_content: editFlag,
      can_view_employee_panel: role === 'read_only',
    };
    if (path === '/trainings/remote/catalog/packages') return [packageRow];
    if (path === '/trainings/remote/catalog/packages/10') return packageRow;
    if (path === '/companies') return [{id: 1, name: 'Yetkili Firma'}];
    return [];
  });
  await act(async () => {
    root.render(React.createElement(RemoteBasicOhsTrainingPanel, {user: {role, osgb_id: 7}}));
  });
}

describe('remote training management and assignment screens', () => {
  it('shows central video controls to the global administrator without company assignment forms', async () => {
    await renderRole('global_admin');
    expect(host.textContent).toContain('Uzaktan Eğitim Video Yönetimi');
    expect(host.textContent).toContain('Yeni ders bölümü oluştur');
    expect(host.textContent).toContain('Video yayımla');
    expect(host.querySelector('input[type="file"]')).not.toBeNull();
    expect(host.querySelector('[aria-label="Atama yapılacak firma"]')).toBeNull();
    expect(api.mock.calls.some(([path]) => path === '/companies')).toBe(false);
  });

  it.each(['company_admin', 'safety_specialist', 'workplace_physician', 'other_health_personnel'])(
    'keeps training selection and company/personnel operations for %s while hiding video mutations',
    async (role) => {
      await renderRole(role);
      expect(host.querySelector('[aria-label="Atama yapılacak firma"]')).not.toBeNull();
      expect(host.querySelector('[aria-label="Merkezi Ortak Eğitim sektör paketini firmaya seç"]')).not.toBeNull();
      expect(host.textContent).toContain('Firma eğitim atama ve çalışan takip yönetimi');
      expect(host.textContent).toContain('Firma eğitim katılım ve belgelendirme raporu');
      expect(host.querySelector('input[type="file"]')).toBeNull();
      const buttonLabels = [...host.querySelectorAll('button')].map((button) => button.textContent.trim());
      expect(buttonLabels).not.toContain('Video yayımla');
      expect(buttonLabels).not.toContain('Taslak videoyu sil');
      expect(buttonLabels).not.toContain('Yeni ders bölümü oluştur');
    },
  );

  it('does not grant video management to a lower role even if metadata is stale', async () => {
    await renderRole('company_admin', {editFlag: true});
    expect(host.querySelector('input[type="file"]')).toBeNull();
    expect(host.textContent).not.toContain('Uzaktan Eğitim Video Yönetimi');
  });

  it('keeps employee accounts in their own assigned learning panel', async () => {
    await renderRole('read_only');
    expect(host.querySelector('[aria-label="Atama yapılacak firma"]')).toBeNull();
    expect(host.querySelector('input[type="file"]')).toBeNull();
    expect(host.textContent).not.toContain('Firma eğitim atama ve çalışan takip yönetimi');
  });
});
