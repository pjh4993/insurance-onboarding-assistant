import { expect, test } from "@playwright/test";
import { createSession, unverifiedName } from "../../support/api";
import { CustomerApp } from "../../support/customer";
import { t } from "../../support/i18n";
import { seed } from "../../support/seeds";

// The console's own language comes from the agent_locale cookie; pin it so labels are predictable.
test.beforeEach(async ({ context, baseURL }) => {
  await context.addCookies([{ name: "agent_locale", value: "en", url: baseURL! }]);
});

test("the agent creates a session link in the console", async ({ page }) => {
  await page.goto("/agent");
  await page.getByRole("button", { name: t("en", "agent.newSession.open") }).click();
  await page.getByRole("radio", { name: t("en", "agent.newSession.marketName.US") }).click();
  await page.getByRole("button", { name: t("en", "agent.newSession.create") }).click();
  await expect(page.getByText(/\/s\/[A-Za-z0-9._~-]{8,}/)).toBeVisible();
});

test("a handed-off customer is taken over and closed by the agent", async ({ browser, page, request }) => {
  // The customer runs in their own browser context (their own session cookie).
  const d = seed("D");
  const s = await createSession(request, d.market);
  const customerContext = await browser.newContext();
  const customer = new CustomerApp(await customerContext.newPage(), "en");
  await customer.page.goto(s.customer_path);
  await customer.startWithoutProduct();
  expect(await customer.completeOnboarding(d)).toBe("waitAgent");

  await page.goto("/agent");
  const item = page.getByRole("button", { name: new RegExp(unverifiedName(s.session_id)) });
  await expect(item).toContainText(t("en", "agent.list.handoff"));
  await item.click();
  await page.getByRole("button", { name: t("en", "agent.conversation.assign") }).click();
  await page.getByRole("button", { name: t("en", "handoff.end") }).click();

  // The customer's page follows over SSE.
  await expect(customer.closedNotice("WITHDRAWN")).toBeVisible();
  await customerContext.close();
});
