import {test, expect} from "@playwright/test";

test("login shell loads", async ({page}) => {
  await page.goto("/");
  await expect(page.locator("body")).toBeVisible();
  // SPA login formu veya marka metni
  const text = await page.locator("body").innerText();
  expect(text.length).toBeGreaterThan(10);
});
