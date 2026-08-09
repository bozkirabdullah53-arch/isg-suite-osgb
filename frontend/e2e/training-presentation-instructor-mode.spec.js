import {test, expect} from '@playwright/test';

const readiness = {
  readiness_version: 'nace-training-presentation-readiness-v4',
  training_id: 101,
  company_id: 118,
  enabled: true,
  visible: true,
  read_only: true,
  manifest_preview_supported: true,
  generation_supported: true,
  generation_allowed: true,
  renderer_version: 'nace-training-presentation-renderer-v1',
  core_training_unaffected: true,
  rollout: {global_enabled: true, force_off: false, allowlist_configured: true, pilot_company: true, active: true},
  classification: {
    status: 'verified',
    nace_code: '27.20.01',
    nace_description: 'Elektrik akümülatör parçalarının imalatı',
    hazard_class: 'Çok Tehlikeli',
  },
  source_data: {training_topics: ['Konu 1', 'Konu 2', 'Konu 3', 'Konu 4', 'Konu 5']},
  checks: [
    {code: 'feature_flag', label: 'Kontrollü pilot erişimi', ok: true, detail: 'Hazır'},
    {code: 'verified_nace_snapshot', label: 'Doğrulanmış NACE snapshot', ok: true, detail: 'Hazır'},
    {code: 'five_training_topics', label: 'Beş işe özgü eğitim konusu', ok: true, detail: 'Hazır'},
    {code: 'technical_risks', label: 'Teknik risk etiketleri', ok: true, detail: 'Hazır'},
    {code: 'exact_exam_readiness', label: 'NACE uyumlu sınav içeriği', ok: true, detail: '5 + 15 hazır'},
    {code: 'training_not_cancelled', label: 'Eğitim durumu', ok: true, detail: 'Aktif'},
    {code: 'template_contract', label: 'İçerik ve şablon sözleşmesi', ok: true, detail: 'Onaylı'},
    {code: 'presentation_renderer', label: 'PPTX/PDF üretim servisi', ok: true, detail: 'Hazır'},
    {code: 'question_slide_traceability', label: '20/20 soru-slayt ve teknik içerik paketi', ok: true, detail: 'Hazır'},
  ],
  blockers: [],
  warnings: [],
  traceability: {enabled: true, ready: true, supported_count: 5, topic_count: 5},
  next_action: 'Yeni sunum sürümü oluşturabilirsiniz.',
};

function traceableManifest() {
  const links = Array.from({length: 20}, (_, index) => ({
    question_position: index + 1,
    question_code: index < 5 ? `TR-TEMEL-ISG-00${index + 1}` : `TR-NACE-272001-${String(Math.floor((index - 5) / 3) + 1).padStart(2, '0')}-${((index - 5) % 3) + 1}`,
    answer_concept_id: `LC-${index + 1}`,
    slide_positions: [index < 5 ? 1 : 2],
    source_refs: ['https://www.csgb.gov.tr/'],
  }));
  return {
    content_hash: 'a'.repeat(64),
    manifest_version: 'nace-training-presentation-manifest-v2-traceability',
    nace_snapshot: {nace_code: '27.20.01', nace_description: 'Elektrik akümülatör parçalarının imalatı'},
    rendering: {traceability_ready: true, instructor_mode_supported: true, instructor_mode_ui: 'instructor-mode-v2', coverage_v2_active: true},
    coverage_v2: {enabled: true, version: 'nace-training-presentation-coverage-v2', topic_count: 5, phase9_supported_count: 5, phase9_full_profile: true},
    traceability: {
      version: 'presentation-question-traceability-v1',
      coverage: {
        question_total: 20,
        linked_questions: 20,
        source_linked_questions: 20,
        orphan_questions: 0,
        cross_sector_fallback: false,
        status: 'passed',
      },
      learning_concepts: links.map((link) => ({concept_id: link.answer_concept_id, statement: 'Doğrulanmış bilgi'})),
      question_links: links,
    },
    slides: [
      {
        position: 1,
        section_id: 'foundation_ohs',
        title: 'Temel İSG İlkeleri',
        approval_required: true,
        source_refs: ['6331 sayılı Kanun'],
        content_blocks: [
          {type: 'tehlike', value: 'İşe başlamadan önce tehlikeler ve kontroller anlaşılmalıdır.'},
          {type: 'training_date', value: '2026-08-09'},
        ],
      },
      {
        position: 2,
        section_id: 'work_specific_topics',
        title: 'Kurşun maruziyeti ve kontrolü',
        source_refs: ['https://www.csgb.gov.tr/isgum/hizli-erisim/tozla-mucadele/'],
        content_blocks: [
          {type: 'tehlike', value: 'Kurşun içeren toz ve duman çalışan maruziyetine neden olabilir.'},
          {type: 'kontrol_tedbiri', value: 'Kaynağında kapatma ve yerel emiş gibi mühendislik kontrolleri uygulanmalıdır.'},
          {type: 'guvenli_davranis', value: 'Kontrol yetersizse çalışmayı normal kabul etmeden uygunsuzluğu bildirmek gerekir.'},
        ],
      },
    ],
  };
}

function approval() {
  return {
    id: 901,
    presentation_version_id: 501,
    training_id: 101,
    company_id: 118,
    approval_method: 'application_approval',
    hashes: {manifest: 'a'.repeat(64), pptx: 'b'.repeat(64), pdf: 'c'.repeat(64)},
    approver: {user_id: 9, name: 'Pilot İSG Uzmanı', role: 'safety_specialist'},
    legal_notice: 'Bu kayıt uygulama içi uzman onayıdır; nitelikli elektronik imza yerine geçmez.',
    event_hash: 'd'.repeat(64),
    created_at: '2026-08-08T20:02:00Z',
    immutable: true,
  };
}

async function installRoutes(page, {status = 'generated', approvalRecord = null} = {}) {
  const version = {
    id: 501,
    training_id: 101,
    company_id: 118,
    version: 2,
    status,
    manifest_hash: 'a'.repeat(64),
    outputs: {
      pptx: {storage_key: 'pilot/v2.pptx', file_hash: 'b'.repeat(64), file_size: 1000},
      pdf: {storage_key: 'pilot/v2.pdf', file_hash: 'c'.repeat(64), file_size: 900},
    },
    failure: {},
    approval: approvalRecord,
    created_at: '2026-08-08T20:00:00Z',
    generated_at: '2026-08-08T20:01:00Z',
    approved_at: approvalRecord?.created_at || null,
  };
  await page.route('**/health', (route) => route.fulfill({status: 200, contentType: 'application/json', body: '{"ok":true}'}));
  await page.route('**/api/v1/trainings/101/presentation-readiness', (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(readiness)}));
  await page.route('**/api/v1/trainings/101/presentation-versions', (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({training_id: 101, count: 1, rows: [version], read_only_history: true})}));
  await page.route('**/api/v1/trainings/101/presentation-versions/501', (route) => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({...version, manifest: traceableManifest()})}));
}

async function injectTrainingOutput(page) {
  await page.evaluate(() => {
    document.body.innerHTML = `
      <main style="width:100%;max-width:100%;padding:12px">
        <section class="education-output-panel panel">
          <h3>Eğitim Belgesi ve PDF Raporlama</h3>
          <p>Kayıt #101 · 2 katılımcı üzerinden PDF çıktıları hazır.</p>
          <button type="button">Sertifika PDF</button>
        </section>
      </main>`;
  });
}

test('traceable generated presentation returns to education and resumes from the saved slide', async ({page}) => {
  await installRoutes(page);
  await page.goto('/');
  await injectTrainingOutput(page);

  const panel = page.locator('.training-presentation-panel');
  await expect(panel).toBeVisible();
  const launch = panel.getByRole('button', {name: 'Eğitmen Modu'});
  await expect(launch).toBeVisible();
  await launch.click();

  const player = page.locator('.training-instructor-mode');
  await expect(player).toBeVisible();
  await expect(player).toHaveAttribute('data-ui-version', 'instructor-mode-v2');
  await expect(player.getByText('Kaynak kontrollü · v2')).toBeVisible();
  await expect(player.getByText('Temel İSG İlkeleri')).toBeVisible();
  await expect(player.getByText('20/20 soru kapsaması doğrulandı')).toBeVisible();
  await expect(player.getByText('Eğitim tarihi')).toBeVisible();
  await expect(player.getByText('training date', {exact: false})).toHaveCount(0);
  await expect(player.getByRole('button', {name: 'Eğitim bölümüne dön'})).toBeVisible();
  await expect(player.getByText('Sunum sürümü uzman onayı bekliyor')).toBeVisible();
  await expect(player.getByText('Uzman/işyeri onayı gerekli')).toHaveCount(0);

  await page.keyboard.press('ArrowRight');
  await expect(player.getByText('Kurşun maruziyeti ve kontrolü')).toBeVisible();
  await expect(player.getByText('15 sınav sorusu bu slayta bağlı')).toBeVisible();
  await expect(player.getByText('5/5 genişletilmiş NACE konu paketi')).toBeVisible();
  await expect(player.locator('[data-content-kind="hazard"]')).toBeVisible();
  await expect(player.locator('[data-content-kind="control"]')).toBeVisible();
  await expect(player.locator('[data-content-kind="behavior"]')).toBeVisible();
  await expect(player.locator('.training-instructor-mode__sources a')).toHaveAttribute('href', /csgb\.gov\.tr/);

  await player.getByRole('button', {name: 'Eğitim bölümüne dön'}).click();
  await expect(player).toHaveCount(0);
  await expect(page.getByText('Sertifika PDF')).toBeVisible();
  await expect(launch).toBeFocused();

  await launch.click();
  await expect(player).toBeVisible();
  await expect(player.getByText('Kurşun maruziyeti ve kontrolü')).toBeVisible();
});

test('pending approval sends the instructor directly to the approval dialog', async ({page}) => {
  await installRoutes(page);
  await page.goto('/');
  await injectTrainingOutput(page);
  const panel = page.locator('.training-presentation-panel');
  await panel.getByRole('button', {name: 'Eğitmen Modu'}).click();

  const player = page.locator('.training-instructor-mode');
  await expect(player.getByText('Sunum sürümü uzman onayı bekliyor')).toBeVisible();
  await expect(player.getByText('NACE Uyumlu Eğitim Sunumu', {exact: false})).toBeVisible();
  await player.getByRole('button', {name: 'Eğitime dön ve onayla'}).click();

  await expect(player).toHaveCount(0);
  const dialog = page.locator('.training-presentation-approval-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('nitelikli elektronik imza yerine geçmez')).toBeVisible();
});

test('approved presentation does not show a false approval-required warning', async ({page}) => {
  await installRoutes(page, {status: 'approved', approvalRecord: approval()});
  await page.goto('/');
  await injectTrainingOutput(page);
  await page.locator('.training-presentation-panel').getByRole('button', {name: 'Eğitmen Modu'}).click();
  const player = page.locator('.training-instructor-mode');
  await expect(player.getByText('Uzman tarafından onaylandı')).toBeVisible();
  await expect(player.getByText('Sunum sürümü uzman onayı bekliyor')).toHaveCount(0);
  await expect(player.getByText('Uzman/işyeri onayı gerekli')).toHaveCount(0);
});

test('instructor mode v2 stays within a 390px mobile viewport', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await installRoutes(page);
  await page.goto('/');
  await injectTrainingOutput(page);
  await page.locator('.training-presentation-panel').getByRole('button', {name: 'Eğitmen Modu'}).click();
  const player = page.locator('.training-instructor-mode');
  await expect(player).toBeVisible();
  await expect(player.locator('.training-instructor-mode__cards')).toBeVisible();
  await expect(player.getByRole('button', {name: 'Eğitim bölümüne dön'})).toBeVisible();
  await expect(player.getByRole('button', {name: 'Eğitime dön ve onayla'})).toBeVisible();
  const widths = await page.evaluate(() => ({viewport: window.innerWidth, documentWidth: document.documentElement.scrollWidth}));
  expect(widths.documentWidth).toBeLessThanOrEqual(widths.viewport);
});
