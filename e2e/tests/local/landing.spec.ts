import { expect, test } from "@playwright/test";
import { createSession, sessionDetail } from "../../support/api";
import { CustomerApp } from "../../support/customer";
import { t } from "../../support/i18n";
import { seed } from "../../support/seeds";

test("a KR link opens on the Korean landing screen with the KR products", async ({ page, request }) => {
  const s = await createSession(request, "KR");
  const app = new CustomerApp(page, "ko");
  await page.goto(s.customer_path);

  await expect(app.headline()).toContainText(t("ko", "customer.headline1"));
  await expect(page.locator("html")).toHaveAttribute("lang", "ko");
  await expect(app.localeOption("ko")).toHaveAttribute("aria-checked", "true");
  for (const product of ["travel", "phone", "laptop", "appliance"]) {
    await expect(app.productCard("KR", product)).toBeVisible();
  }
});

test("a US link opens in English with the US products", async ({ page, request }) => {
  const s = await createSession(request, "US");
  const app = new CustomerApp(page, "en");
  await page.goto(s.customer_path);

  await expect(app.headline()).toContainText(t("en", "customer.headline1"));
  await expect(app.productCard("US", "travel")).toBeVisible();
});

test("switching the language is saved on the session and survives a reload", async ({ page, request }) => {
  const s = await createSession(request, "KR");
  const app = new CustomerApp(page, "ko");
  await page.goto(s.customer_path);
  await expect(app.headline()).toContainText(t("ko", "customer.headline1"));

  await app.switchLocale("en");
  await expect(app.headline()).toContainText(t("en", "customer.headline1"));
  await expect.poll(async () => (await sessionDetail(request, s.session_id)).session.locale).toBe("en");

  await page.reload();
  await expect(app.headline()).toContainText(t("en", "customer.headline1"));
  await expect(page).toHaveTitle(new RegExp(t("en", "customer.title")));
});

test("the product picked on the landing screen pre-fills the first needs answer", async ({ page, request }) => {
  const b = seed("B"); // KR, no partner record: OTP
  const s = await createSession(request, "KR", "en");
  const app = new CustomerApp(page, "en");
  await page.goto(s.customer_path);

  await app.productCard("KR", "travel").click();
  await app.fillIdentity(b, { consent: false });
  await app.enterOtp();
  await expect(app.needsBox()).toHaveValue(t("en", "products.KR.travel.ask"));
});

test("once started, a reload goes straight back to the chat", async ({ page, request }) => {
  const s = await createSession(request, "US");
  const app = new CustomerApp(page, "en");
  await page.goto(s.customer_path);
  await app.startWithoutProduct();
  await expect(page.getByRole("button", { name: t("en", "identity.submit") })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("button", { name: t("en", "identity.submit") })).toBeVisible();
  await expect(app.headline()).toHaveCount(0);
});
