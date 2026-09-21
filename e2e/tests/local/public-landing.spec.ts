import { expect, test } from "@playwright/test";
import { CustomerApp } from "../../support/customer";
import { t } from "../../support/i18n";

// One start only: the backend allows five self-serve starts per client IP per hour.
test("anyone can start a session from the public landing page", async ({ page }) => {
  const app = new CustomerApp(page, "en");
  await page.goto("/");
  await expect(app.headline()).toContainText(t("en", "customer.headline1"));

  await page.getByRole("radiogroup", { name: t("en", "home.marketHint") }).getByRole("radio", { name: "KR" }).click();
  await app.productCard("KR", "travel").click();

  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByRole("button", { name: t("en", "identity.submit") })).toBeVisible();
});
