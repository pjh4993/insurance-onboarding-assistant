// The four seed customers end to end through the customer UI (docs/guides/demo.md).
import { expect, test } from "@playwright/test";
import { createSession, sessionDetail } from "../../support/api";
import { CustomerApp } from "../../support/customer";
import { seed } from "../../support/seeds";

test("A: partner match with consent, in Korean, ends submitted", async ({ page, request }) => {
  const a = seed("A");
  const s = await createSession(request, a.market); // KR default: Korean
  const app = new CustomerApp(page, "ko");
  await page.goto(s.customer_path);
  await app.startWithoutProduct();

  expect(await app.completeOnboarding(a, { consent: true })).toBe("closed");
  await expect(app.closedNotice("SUBMITTED")).toBeVisible();

  const d = await sessionDetail(request, s.session_id);
  expect(d.entities.party?.verification_method).toBe("PARTNER_MATCH");
  expect(d.entities.recommendations.find((r) => r.status === "ACCEPTED")?.product_code).toBe("KR-MOB-SWAP");
  expect(d.entities.application?.submission_ref).toBeTruthy();
});

test("B: OTP, in English on a KR session, ends submitted", async ({ page, request }) => {
  const b = seed("B");
  const s = await createSession(request, b.market, "en");
  const app = new CustomerApp(page, "en");
  await page.goto(s.customer_path);
  await app.startWithoutProduct();

  expect(await app.completeOnboarding(b)).toBe("closed");
  await expect(app.closedNotice("SUBMITTED")).toBeVisible();

  const d = await sessionDetail(request, s.session_id);
  expect(d.entities.party?.verification_method).toBe("OTP");
  expect(d.entities.recommendations.find((r) => r.status === "ACCEPTED")?.product_code).toBe("KR-TRV-OVERSEAS");
});

test("C: OTP fails, the passport passes, ends submitted", async ({ page, request }) => {
  const c = seed("C");
  const s = await createSession(request, c.market);
  const app = new CustomerApp(page, "en");
  await page.goto(s.customer_path);
  await app.startWithoutProduct();

  expect(await app.completeOnboarding(c)).toBe("closed");
  await expect(app.closedNotice("SUBMITTED")).toBeVisible();

  const d = await sessionDetail(request, s.session_id);
  expect(d.entities.party?.verification_method).toBe("DOCUMENT");
  expect(d.entities.recommendations.find((r) => r.status === "ACCEPTED")?.product_code).toBe("US-DEV-LAPTOP-2Y");
});

test("D: two failed checks hand the customer to an agent", async ({ page, request }) => {
  const dSeed = seed("D");
  const s = await createSession(request, dSeed.market);
  const app = new CustomerApp(page, "en");
  await page.goto(s.customer_path);
  await app.startWithoutProduct();

  expect(await app.completeOnboarding(dSeed)).toBe("waitAgent");
  const d = await sessionDetail(request, s.session_id);
  expect(d.session.status).toBe("HANDOFF");
  expect(d.session.waiting_for).toBe("AGENT");
});
