import {defineConfig, devices} from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4173";

// E2E testleri anonim API korumasını (api.js guard) oturum bağlamı bayrağıyla
// devre dışı bırakır ve "kısayol eklensin mi" diyaloğunu kapalı tutar.
// Üretimde gerçek kullanıcılar guard + diyalog mantığıyla karşılaşmaya devam eder.
const e2eStorageState = {
  cookies: [],
  origins: [
    {
      origin: new URL(baseURL).origin,
      localStorage: [
        {name: "isg_refresh_cookie", value: "1"},
        {
          name: "isg_pwa_shortcut_choice_v2",
          value: JSON.stringify({choice: "dismissed", time: Number.MAX_SAFE_INTEGER}),
        },
      ],
    },
  ],
};

export default defineConfig({
  testDir: "./e2e",
  // The company-scoped read-only pilot was replaced by the OSGB-professional
  // card flow. Current coverage lives in personnel-profile-sidebar/documents.
  testIgnore: ["**/personnel-profile-readonly.spec.js"],
  timeout: 60_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL,
    trace: "on-first-retry",
    storageState: e2eStorageState,
  },
  webServer: {
    command: "npm run preview -- --host 127.0.0.1 --port 4173",
    port: 4173,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [{name: "chromium", use: {...devices["Desktop Chrome"]}}],
});
