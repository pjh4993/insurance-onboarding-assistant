import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "onb_session";
const TOKEN_RE = /^[A-Za-z0-9._~-]{8,512}$/;

/**
 * Customer entry: /s/{token}. Store the session-link token in an httpOnly cookie so that client code never
 * holds it; /api/customer/* route handlers read the cookie and send X-Session-Token upstream.
 */
export function proxy(request: NextRequest) {
  const token = decodeURIComponent(request.nextUrl.pathname.split("/")[2] ?? "");
  const res = NextResponse.next();
  res.headers.set("Referrer-Policy", "no-referrer");
  if (TOKEN_RE.test(token)) {
    res.cookies.set(SESSION_COOKIE, token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.COOKIE_SECURE === "true",
      path: "/",
      maxAge: 60 * 60 * 24,
    });
  }
  return res;
}

export const config = { matcher: "/s/:token" };
