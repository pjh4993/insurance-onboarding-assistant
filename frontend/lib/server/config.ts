import "server-only";

import { baseUrl } from "../hosts";

export { SESSION_COOKIE } from "./sessionCookie";

export function backendUrl(): string {
  return (process.env.BACKEND_URL ?? "http://localhost:18000").replace(/\/+$/, "");
}

export function cookieSecure(): boolean {
  return process.env.COOKIE_SECURE === "true";
}

/** The agent console's own host (e.g. https://dev.agent.onboardassist.click), or null for one shared host. */
export function agentBaseUrl(): string | null {
  return baseUrl(process.env.AGENT_BASE_URL);
}

/** The operator console's own host (e.g. https://dev.operator.onboardassist.click), or null. */
export function operatorBaseUrl(): string | null {
  return baseUrl(process.env.OPERATOR_BASE_URL);
}

/** The customer app's host, for links made on the agent host; null for one shared host. */
export function customerBaseUrl(): string | null {
  return baseUrl(process.env.CUSTOMER_BASE_URL);
}
