import {test, expect} from '@playwright/test';

function dashboardPayload(overrides = {}) {
  return {
    enabled: true,
    company_id: 118,
    today: '2026-08-09',
    work_start_tracking_from: '2026-08-09',
    summary: {
      active_employees: 3,
      work_start_missing: 1,
      work_start_pending: 0,
      work_start_ok: 1,
      work_start_historical: 1,
      basic_overdue: 1,
      basic_waiting: 1,
      basic_due_soon: 0,
      basic_ok: 1,
      result_pending: 1,
      planned_future: 0,
    },
    actions: [
      {
        code: 'work_start_missing',
        severity: 'danger',
        count: 1,
        title: 'İşe Başlama Eğitimi eksik',
        instruction: 'Bu çalışanlar için işe başlamadan önce İşe Başlama Eğitimi planlayın.',
        target: 'temel',
      },
      {
        code: 'basic_overdue',
        severity: 'danger',
        count: 1,
        title: 'Temel İSG eğitimi gecikmiş / eksik',
        instruction: 'Önce kırmızı durumdaki çalışanları eğitime alın.',
        target: 'yenileme',
      },
    ],
    rows: [
      {
        employee_id: 1,
        full_name: 'Yeni Çalışan',
        job_title: 'Operatör',
        department: 'Üretim',
        start_date: '2026-08-10',
        work_start: {status: 'missing', label: 'Eksik', tone: 'danger', message: 'İşe Başlama Eğitimi kaydı bulunamadı.'},
        basic: {status: 'never', label: 'İlk temel eğitim bekliyor', tone: 'warning', message: 'Temel eğitim en geç üç ay içinde tamamlanmalı.'},
      },
      {
        employee_id: 2,
        full_name: 'Tarihsel Çalışan',
        job_title: 'Usta',
        department: 'Bakım',
        start_date: '2022-01-10',
        work_start: {status: 'historical', label: 'Tarihsel / takip dışı', tone: 'neutral', message: 'Geriye dönük eksik kaydı üretilmez.'},
        basic: {status: 'ok', label: 'Geçerli', tone: 'ok', message: 'Temel eğitim geçerli.'},
      },
    ],
    safety: {read_only: true, automatic_training_completion: false},
    ...overrides,
  };
}

async function injectTrainingShell(page) {
  await page.evaluate(() => {
    document.body.innerHTML = `
      <main class="training-pro">
        <div class="tp-tabs">
          <button type="button" class="tp-tab">Temel İSG Eğitimi</button>
          <button type="button" class="tp-tab">Özel Eğitimler</button>
          <button type="button" class="tp-tab">Yenileme Takibi</button>
          <button type="button" class="tp-tab">Kayıtlar</button>
        </div>
        <section class="training-premium-lifecycle"><h2>Planla → Gerçekleştir → Sonuçlandır → Belgelendir</h2></section>
        <select id="tp-firma"><option value="118" selected>Test Firma</option></select>
        <div id="clickedTab"></div>
      </main>`;
    document.querySelectorAll('.tp-tab').forEach((button) => {
      button.addEventListener('click', () => {
        document.getElementById('clickedTab').textContent = button.textContent;
      });
    });
  });
}

async function mockDashboard(page, payload) {
  await page.route('**/api/v1/trainings/premium-dashboard?**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  }));
}

test('shows simple priority cards and two separate traffic lights', async ({page}) => {
  await mockDashboard(page, dashboardPayload());
  await page.goto('/');
  await injectTrainingShell(page);

  await expect(page.getByText('Bugün Ne Yapmalıyım?')).toBeVisible();
  await expect(page.getByRole('heading', {name: 'Eğitim işlerini önem sırasına koyduk'})).toBeVisible();
  await expect(page.getByText('İşe Başlama Eğitimi eksik')).toBeVisible();
  await expect(page.getByText('Temel İSG eğitimi gecikmiş / eksik')).toBeVisible();

  await page.getByRole('button', {name: 'Çalışan durumlarını göster'}).click();
  await expect(page.getByRole('columnheader', {name: 'İşe Başlama Eğitimi'})).toBeVisible();
  await expect(page.getByRole('columnheader', {name: 'Temel İSG Eğitimi'})).toBeVisible();
  await expect(page.getByText('Tarihsel / takip dışı')).toBeVisible();
  await expect(page.getByText('Geriye dönük eksik kaydı üretilmez.')).toBeVisible();
});

test('priority card sends user to the existing Training tab', async ({page}) => {
  await mockDashboard(page, dashboardPayload());
  await page.goto('/');
  await injectTrainingShell(page);

  await page.getByRole('button', {name: /Temel İSG eğitimi gecikmiş/}).click();
  await expect(page.locator('#clickedTab')).toHaveText('Yenileme Takibi');
});

test('feature-off endpoint leaves the existing Training UI visually untouched', async ({page}) => {
  await mockDashboard(page, dashboardPayload({enabled: false, actions: [], rows: [], summary: {}}));
  await page.goto('/');
  await injectTrainingShell(page);
  await page.waitForTimeout(150);

  await expect(page.locator('#trainingPremiumDashboardV1')).toHaveCount(0);
  await expect(page.getByText('Planla → Gerçekleştir → Sonuçlandır → Belgelendir')).toBeVisible();
});

test('does not render a placeholder before a company is selected', async ({page}) => {
  await page.goto('/');
  await page.evaluate(() => {
    document.body.innerHTML = `
      <main class="training-pro">
        <div class="tp-tabs"><button class="tp-tab">Temel İSG Eğitimi</button></div>
        <section class="training-premium-lifecycle"></section>
        <select id="tp-firma"><option value="" selected>Seçiniz</option></select>
      </main>`;
  });
  await page.waitForTimeout(100);
  await expect(page.locator('#trainingPremiumDashboardV1')).toHaveCount(0);
});

test('fits a 390px mobile viewport without page-level horizontal overflow', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await mockDashboard(page, dashboardPayload());
  await page.goto('/');
  await injectTrainingShell(page);
  await expect(page.locator('#trainingPremiumDashboardV1')).toBeVisible();

  const widths = await page.evaluate(() => ({
    viewport: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
  }));
  expect(widths.documentWidth).toBeLessThanOrEqual(widths.viewport);
});
