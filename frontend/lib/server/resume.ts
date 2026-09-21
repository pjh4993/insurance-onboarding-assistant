import "server-only";
import { cookies } from "next/headers";
import { isClosed } from "../session";
import type { SessionView } from "../types";
import { backendUrl, SESSION_COOKIE } from "./config";
import { log } from "./log";

const PATH = "/api/customer/session";

/**
 * Whether the visitor's session cookie (from /s/{token} or an earlier start on /) names a session that has
 * not ended, so the landing page can offer to continue it. No cookie, 401/404, a slow or failed backend:
 * all "no session" — the landing page must render regardless.
 */
export async function hasResumableSession(): Promise<boolean> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return false;
  try {
    const res = await fetch(`${backendUrl()}${PATH}`, {
      headers: { "X-Session-Token": token, Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return false;
    const view = (await res.json()) as Partial<SessionView>;
    return !!view.session?.status && !isClosed(view.session.status);
  } catch (err) {
    log("warn", "resume check failed", { "http.request.method": "GET", "url.path": PATH }, err);
    return false;
  }
}
