// Read-only checks of the deployed develop environment. Nothing here logs in or creates data.
import { expect, test } from "@playwright/test";
import { t } from "../../support/i18n";
import { DEV } from "../../support/hosts";

test("the app host serves the public landing page", async ({ page }) => {
  await page.goto(DEV.app);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("radiogroup", { name: t("en", "common.languageHint") })).toBeVisible();
});

test("the app host reaches the backend", async ({ request }) => {
  const own = await request.get(`${DEV.app}/api/healthz`);
  expect(own.status()).toBe(200);
  const backend = await request.get(`${DEV.app}/healthz`);
  expect(backend.status()).toBe(200);
  expect(await backend.json()).toMatchObject({ status: "ok" });
});

test("the agent host sends agents to the Cognito login", async ({ request }) => {
  const res = await request.get(`${DEV.agent}/agent`, { maxRedirects: 0 });
  expect(res.status()).toBe(302);
  expect(res.headers()["location"]).toMatch(/\.amazoncognito\.com\/oauth2\/authorize/);
});

test("agent data is not reachable from the customer host", async ({ request }) => {
  const res = await request.get(`${DEV.app}/api/agent/sessions`, { maxRedirects: 0 });
  expect([302, 401, 403, 404]).toContain(res.status());
});

test("the docs host serves the design docs, publicly", async ({ page }) => {
  const res = await page.goto(DEV.docs);
  expect(res?.status()).toBe(200);
  await expect(page.locator("article h1").first()).toBeVisible();
});
