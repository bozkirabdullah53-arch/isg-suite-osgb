import {test, expect} from '@playwright/test';

const readiness = {
  readiness_version: 'osgb-professional-card-v1',
  osgb_id: 4,
  enabled: true,
  visible: true,
  scope: 'osgb_professionals_only',
  employee_records_included: false,
  assignment_required_for_visibility: false,
  rollout: {
    global_enabled: true,
    force_off: false,
    allowlist_configured: true,
    pilot_osgb: true,
    active: true,
  },
};
const professional = {
  id: 7,
  osgb_id: 4,
  full_name: 'Mehmet Uzman',
  professional_type: 'safety_specialist',
  certificate_class: 'A',
  certificate_number: 'UZM-123',
  is_active: true,
};
const summary = {
  summary_version: 'osgb-professional-profile-summary-v1',
  subject: {type: 'professional', id: 7},
  scope: {osgb_id: 4, company_id: null, company_name: null},
  profile: {
    full_name: 'Mehmet Uzman',
    professional_type: 'safety_specialist',
    email: 'uzman@example.com',
    phone: '+90 555 000 00 00',
    certificate_class: 'A',
    certificate_number: 'UZM-123',
    certificate_date: '2020-05-01',
    employment_status: 'active',
    active_assignment_count: 0,
  },
  privacy: {
    data_minimized: true,
    national_identity_full_included: false,
    special_status_included: false,
    health_data_included: false,
    criminal_record_included: false,
    restricted_documents_included: false,
  },
};
const snapshot = {
  profile: {
    id: 55,
    osgb_id: 4,
    company_id: null,
    branch_id: null,
    subject_type: 'professional',
    employee_id: null,
    professional_id: 7,
    user_id: null,
    status: 'active',
    created_at: '2026-08-06T12:00:00',
    archived_at: null,
  },
  contacts: [],
  competencies: [],
  experiences: [],
  privacy: {
    ordinary_professional_data_only: true,
    national_identity_included: false,
    home_address_included: false,
    emergency_contact_included: false,
    health_data_included: false,
    criminal_record_included: false,
    salary_included: false,
    disciplinary_data_included: false,
    documents_included: false,
    external_sharing_enabled: false,
  },
};
const documents = {
  items: [{
    id: 301,
    profile_id: 55,
    document_key: '11111111-1111-4111-a111-111111111111',
    version: 1,
    supersedes_id: null,
    document_kind: 'certificate',
    category: 'first_aid_certificate',
    title: 'İlk Yardımcı Belgesi',
    document_number: 'IY-2026-15',
    issuing_organization: 'Yetkili Eğitim Merkezi',
    issue_date: '2026-01-10',
    valid_from: '2026-01-10',
    expiration_date: '2029-01-10',
    no_expiration: false,
    mime_type: 'application/pdf',
    file_extension: '.pdf',
    file_size: 245760,
    checksum_sha256: 'a'.repeat(64),
    access_classification: 'internal_only',
    verification_status: 'unverified',
    lifecycle_status: 'active',
    validity_status: 'valid',
    processing_purpose: 'osgb_professional_profile_management',
    retention_policy: 'osgb_professional_profile_ordinary_v1',
    change_reason: null,
    created_at: '2026-08-06T12:10:00',
  }],
};

async function installRoutes(page) {
  let employeeRequestCount = 0;
  const json = (route, body, status = 200) => route.fulfill({
    status,
    contentType: 'application/json',
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Authorization, Content-Type, Idempotency-Key',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    },
    body: JSON.stringify(body),
  });
  await page.route('**/health', (route) => json(route, {ok: true}));
  await page.route('**/api/v1/auth/me', (route) => json(route, {
    id: 2,
    full_name: 'OSGB Yönetici',
    role: 'company_admin',
    osgb_id: 4,
  }));
  await page.route('**/api/v1/osgb', (route) => json(route, [{id: 4, name: 'Test OSGB'}]));
  await page.route('**/api/v1/osgb-personnel-profiles/readiness?osgb_id=4', (route) => json(route, readiness));
  await page.route('**/api/v1/osgb-personnel-profiles/professionals?osgb_id=4', (route) => json(route, {items: [professional]}));
  await page.route('**/api/v1/osgb/assignments?osgb_id=4', (route) => json(route, []));
  await page.route(/\/api\/v1\/employees(?:\?|$)/, async (route) => {
    employeeRequestCount += 1;
    await json(route, {detail: 'OSGB belgesi işyeri çalışanına bağlanamaz.'}, 500);
  });
  await page.route('**/api/v1/osgb-personnel-profiles/professional/7/summary', (route) => json(route, summary));
  await page.route('**/api/v1/osgb-personnel-profiles/professionals/7', (route) => {
    if (route.request().method() === 'POST') {
      return json(route, {created: true, profile: snapshot.profile, privacy: snapshot.privacy});
    }
    return route.fallback();
  });
  await page.route('**/api/v1/osgb-personnel-profiles/55', (route) => json(route, snapshot));
  await page.route('**/api/v1/osgb-personnel-profiles/55/documents?include_archived=false', (route) => json(route, documents));
  return {employeeRequestCount: () => employeeRequestCount};
}

async function injectDesktopShell(page) {
  await page.evaluate(() => {
    document.body.innerHTML = `
      <div class="app-shell">
        <aside><nav class="nav-desktop">
          <button data-nav="osgb_dashboard"><span>OSGB Ana Panel</span></button>
          <button data-nav="companies"><span>İşyerleri</span></button>
          <button data-nav="professionals"><span>İSG Profesyonelleri</span></button>
          <button data-nav="assignments"><span>Görevlendirmeler</span></button>
        </nav></aside>
        <section class="workspace"><main><h3>OSGB Ana Panel</h3></main></section>
      </div>`;
  });
}

test('document tab renders private metadata only for an OSGB professional profile', async ({page}) => {
  const requests = await installRoutes(page);
  await page.goto('/');
  await injectDesktopShell(page);
  await page.locator('[data-personnel-profile-nav="desktop"]').click();
  const manager = page.locator('[data-personnel-profile-manager="true"]');
  await expect(manager.getByText('Mehmet Uzman', {exact: true}).first()).toBeVisible();
  await expect(manager.getByText('Kaynakçı', {exact: true})).toHaveCount(0);
  await manager.getByRole('button', {name: /Kartı başlat/}).click();
  await expect(manager.getByText('Profil #55', {exact: true})).toBeVisible();
  await manager.getByRole('button', {name: 'Belgeler'}).click();
  const documentPanel = manager.locator('[data-personnel-profile-documents-panel="true"]');
  await expect(documentPanel).toBeVisible();
  await expect(documentPanel.getByText('İlk Yardımcı Belgesi', {exact: true})).toBeVisible();
  await expect(documentPanel.getByRole('article').getByText('Yalnız iç kullanım', {exact: true})).toBeVisible();
  await expect(documentPanel.getByRole('heading', {name: 'Belge Yükle'})).toBeVisible();
  expect(await manager.innerHTML()).not.toContain('object_key');
  expect(await manager.innerHTML()).not.toContain('company_id');
  expect(requests.employeeRequestCount()).toBe(0);
});
