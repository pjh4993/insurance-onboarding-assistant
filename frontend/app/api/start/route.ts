import { NextResponse } from "next/server";
import { backendUrl } from "@/lib/server/config";
import { jsonError } from "@/lib/server/forward";
import { log } from "@/lib/server/log";
import { SESSION_COOKIE, SESSION_TOKEN_RE, sessionCookieOptions } from "@/lib/server/sessionCookie";
import { clientIp, parseStartBody, retryAfterSeconds } from "@/lib/start";

export const dynamic = "force-dynamic";

const PATH = "/api/public/sessions";

/**
 * Public self-serve start from the landing page (no session, no agent). Creates a session upstream, puts its
 * token in the httpOnly session cookie (as proxy.ts does for /s/{token}) and returns only the session ID:
 * the token never reaches client code. The backend rate-limits per client address, sent as X-Client-IP.
 */
export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return jsonError(400, "Invalid request");
  }
  const start = parseStartBody(body);
  if (!start) return jsonError(400, "Invalid request");

  const headers: Record<string, string> = { "Content-Type": "application/json", Accept: "application/json" };
  const ip = clientIp(req.headers.get("x-forwarded-for"));
  if (ip) headers["X-Client-IP"] = ip;

  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}${PATH}`, {
      method: "POST",
      headers,
      body: JSON.stringify(start),
      cache: "no-store",
      signal: req.signal,
      redirect: "manual",
    });
  } catch (err) {
    if (req.signal.aborted) return new Response(null, { status: 499 });
    log("error", "backend relay failed", { "http.request.method": "POST", "url.path": PATH }, err);
    return jsonError(502, "Could not start a session");
  }

  const data = (await upstream.json().catch(() => null)) as Record<string, unknown> | null;

  if (upstream.status === 429) {
    const retry_after = retryAfterSeconds(data?.retry_after, upstream.headers.get("retry-after"));
    const res = Response.json({ error: "rate_limited", retry_after }, { status: 429 });
    if (retry_after !== null) res.headers.set("Retry-After", String(retry_after));
    return res;
  }

  const token = data?.token;
  const sessionId = data?.session_id;
  if (upstream.status !== 201 || typeof token !== "string" || !SESSION_TOKEN_RE.test(token) || typeof sessionId !== "string") {
    log("warn", "public session start failed", { "url.path": PATH, "http.response.status_code": upstream.status });
    return jsonError(502, "Could not start a session");
  }

  const res = NextResponse.json({ session_id: sessionId }, { status: 201, headers: { "Cache-Control": "no-store" } });
  res.cookies.set(SESSION_COOKIE, token, sessionCookieOptions());
  return res;
}
