import { NextResponse, type NextRequest } from "next/server";
import { baseUrl, isAgentHost } from "./lib/hosts";
import { SESSION_COOKIE, SESSION_TOKEN_RE, sessionCookieOptions } from "./lib/server/sessionCookie";

/**
 * - `/` on the agent host (AGENT_BASE_URL): serve the agent console, so it is that host's root. Anywhere else
 *   `/` is the public landing page.
 * - Customer entry `/s/{token}`: store the session-link token in an httpOnly cookie so that client code never
 *   holds it; /api/customer/* route handlers read the cookie and send X-Session-Token upstream.
 *   (Self-serve starts on / get the same cookie from /api/start instead.)
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname === "/") {
    const host = request.headers.get("host") ?? request.nextUrl.host;
    return isAgentHost(host, baseUrl(process.env.AGENT_BASE_URL))
      ? NextResponse.rewrite(new URL("/agent", request.url))
      : NextResponse.next();
  }

  const token = decodeURIComponent(pathname.split("/")[2] ?? "");
  const res = NextResponse.next();
  res.headers.set("Referrer-Policy", "no-referrer");
  if (SESSION_TOKEN_RE.test(token)) {
    res.cookies.set(SESSION_COOKIE, token, sessionCookieOptions());
  }
  return res;
}

export const config = { matcher: ["/", "/s/:token"] };
