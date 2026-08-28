import {test, expect} from '@playwright/test';

const packageList = [
  {
    id: 41,
    code: 'battery-production-ohs',
    title: 'Akü-Batarya',
    status: 'draft',
    revision_no: 1,
    is_shared: false,
  },
];

const packageDetail = {
  ...packageList[0],
  sections: [
    {
      id: 411,
      code: 'AKU-01',
      title: 'Bölüm 1',
      description: null,
      order_index: 1,
      is_required: true,
      videos: [],
    },
    {
      id: 412,
      code: 'AKU-02',
      title: 'Bölüm 2',
      description: null,
      order_index: 2,
      is_required: true,
      videos: [],
    },
  ],
};

async function installRemoteCatalogApi(page, writes) {
  await page.route('**/health', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({status: 'ok', service: 'İSG Suite OSGB'}),
  }));
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      id: 7,
      role: 'company_admin',
      osgb_id: 77,
      company_id: null,
      full_name: 'OSGB Yöneticisi',
    }),
  }));
  await page.route('**/api/v1/trainings/remote/catalog/packages', (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(packageList),
    });
  });
  await page.route('**/api/v1/trainings/remote/catalog/packages/41', (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(packageDetail),
    });
  });
  await page.route('**/api/v1/trainings/remote/catalog/packages/41/sections/order', async (route) => {
    const payload = route.request().postDataJSON();
    writes.push(payload);
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({...packageDetail, reordered: true}),
    });
  });
}

async function injectCatalogDom(page) {
  await page.evaluate(() => {
    document.body.innerHTML = `
      <main>
        <section id="remote-catalog-fixture">
          <h3>Uzaktan Eğitim Paket Kataloğu</h3>
          <div class="package-list-panel">
            <h4>Sektör eğitim paketleri</h4>
            <button id="package-card" type="button" style="border-top-color: rgb(255, 0, 0)">
              <strong>Akü-Batarya</strong>
            </button>
            <button type="button">Paketleri yenile</button>
          </div>

          <div class="package-detail-shell">
            <div class="package-detail-top-row">
              <div class="package-detail-heading"><h4>Akü-Batarya</h4></div>
            </div>

            <div id="section-container">
              <article id="section-411" class="section-card">
                <div class="section-header-row">
                  <div class="section-heading-group">
                    <strong>AKU-01 · Bölüm 1</strong>
                  </div>
                </div>
                <p>Birinci bölüm</p>
              </article>
              <article id="section-412" class="section-card">
                <div class="section-header-row">
                  <div class="section-heading-group">
                    <strong>AKU-02 · Bölüm 2</strong>
                  </div>
                </div>
                <p>İkinci bölüm</p>
              </article>
            </div>
          </div>
        </section>
      </main>`;
  });
}

test('remote catalog package selection uses stable API id, not theme border color', async ({page}) => {
  const writes = [];
  await installRemoteCatalogApi(page, writes);
  await page.goto('/');
  await injectCatalogDom(page);

  // The card deliberately has a red top border. The old bridge required a
  // specific teal computed color and would fail to resolve the selected package.
  await page.locator('#package-card').click();

  await expect(page.getByText('Paket yönetimi:', {exact: false})).toBeVisible();
  await expect(page.getByRole('button', {name: '☷ Tut ve taşı'})).toHaveCount(2);
  await expect(page.locator('#package-card')).toHaveAttribute('data-remote-catalog-package-id', '41');
  expect(writes).toEqual([]);
});

test('remote section dragend persists changed DOM order even when drop event is missed', async ({page}) => {
  const writes = [];
  await installRemoteCatalogApi(page, writes);
  await page.goto('/');
  await injectCatalogDom(page);
  await page.locator('#package-card').click();

  const handles = page.getByRole('button', {name: '☷ Tut ve taşı'});
  await expect(handles).toHaveCount(2);

  // Start dragging section 2, then mimic the browser DOM movement that occurs
  // during dragover. Intentionally omit a drop event: this is the regression
  // that previously reverted the section in dragend instead of saving it.
  await handles.nth(1).evaluate((handle) => {
    const transfer = new DataTransfer();
    handle.dispatchEvent(new DragEvent('dragstart', {
      bubbles: true,
      cancelable: true,
      dataTransfer: transfer,
    }));
  });
  await page.evaluate(() => {
    const container = document.querySelector('#section-container');
    const second = document.querySelector('#section-412');
    const first = document.querySelector('#section-411');
    container.insertBefore(second, first);
  });
  await handles.nth(1).evaluate((handle) => {
    handle.dispatchEvent(new DragEvent('dragend', {bubbles: true, cancelable: true}));
  });

  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0]).toEqual({section_ids: [412, 411]});
  await expect(page.getByText('Bölüm sırası kaydedildi.', {exact: false})).toBeVisible();
});
