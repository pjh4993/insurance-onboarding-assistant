import { NextResponse, type NextRequest } from "next/server";
import { agentHostRedirect, baseUrl, isAgentHost, isOperatorHost, operatorHostRedirect } from "./lib/hosts";
import { SESSION_COOKIE, SESSION_TOKEN_RE, sessionCookieOptions } from "./lib/server/sessionCookie";

/**
 * - `/operator*` anywhere but the operator host (OPERATOR_BASE_URL): the same, and `/` on the operator host
 *   serves the operator console.
 * - `/agent*` anywhere but the agent host: redirect to the same page there, before anything renders. The ALB
 *   already refuses /api/agent/* on the customer host, so no agent data is reachable from it.
 * - `/` on the agent host (AGENT_BASE_URL): serve the agent console, so it is that host's root. Anywhere else
 *   `/` is the public landing page.
 * - Customer entry `/s/{token}`: store the session-link token in an httpOnly cookie so that client code never
 *   holds it; /api/customer/* route handlers read the cookie and send X-Session-Token upstream.
 *   (Self-serve starts on / get the same cookie from /api/start instead.)
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const host = request.headers.get("host") ?? request.nextUrl.host;
  const agentBase = baseUrl(process.env.AGENT_BASE_URL);
  const operatorBase = baseUrl(process.env.OPERATOR_BASE_URL);
  const toOtherHost =
    agentHostRedirect(pathname, search, host, agentBase) ?? operatorHostRedirect(pathname, search, host, operatorBase);
  if (toOtherHost) return NextResponse.redirect(toOtherHost, 302);

  if (pathname === "/") {
    if (isAgentHost(host, agentBase)) return NextResponse.rewrite(new URL("/agent", request.url));
    if (isOperatorHost(host, operatorBase)) return NextResponse.rewrite(new URL("/operator", request.url));
    return NextResponse.next();
  }

  if (!pathname.startsWith("/s/")) return NextResponse.next(); // agent or operator pages on their host

  const token = decodeURIComponent(pathname.split("/")[2] ?? "");
  const res = NextResponse.next();
  res.headers.set("Referrer-Policy", "no-referrer");
  if (SESSION_TOKEN_RE.test(token)) {
    res.cookies.set(SESSION_COOKIE, token, sessionCookieOptions());
  }
  return res;
}

export const config = { matcher: ["/", "/s/:token", "/agent", "/agent/:path*", "/operator", "/operator/:path*"] };
