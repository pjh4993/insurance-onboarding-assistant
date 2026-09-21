// Setup and assertions through the frontend's relay (/api/agent/*), which in the compose stack signs every
// call in as `agent-demo` (AGENT_DEV_AUTH=true). Tests drive the UI; these calls only arrange and inspect.
import { expect, type APIRequestContext } from "@playwright/test";
import type { Locale } from "./i18n";
import type { Market } from "./seeds";

export type CreatedSession = { session_id: string; customer_path: string };

export async function createSession(
  request: APIRequestContext,
  market: Market,
  locale?: Locale,
): Promise<CreatedSession> {
  const res = await request.post("/api/agent/sessions", { data: locale ? { market, locale } : { market } });
  expect(res.status(), await res.text()).toBe(201);
  return res.json();
}

export type SessionDetail = {
  session: { status: string; stage: string; waiting_for: string | null; locale?: Locale; market: Market };
  entities: {
    party: { verification_status?: string; verification_method?: string } | null;
    recommendations: { product_code: string; status: string }[];
    application: { status: string; submission_ref: string | null } | null;
  };
};

export async function sessionDetail(request: APIRequestContext, sessionId: string): Promise<SessionDetail> {
  const res = await request.get(`/api/agent/sessions/${sessionId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

/** Unverified sessions are listed as "Unverified #" plus the first four hex digits of their id. */
export const unverifiedName = (sessionId: string) => `Unverified #${sessionId.replaceAll("-", "").slice(0, 4)}`;
