// The customer session cookie, shared by proxy.ts (/s/{token}) and the public start route (/api/start).
// No "server-only" import: proxy.ts loads this too.

export const SESSION_COOKIE = "onb_session";

/** What a session-link token looks like; anything else is not stored. */
export const SESSION_TOKEN_RE = /^[A-Za-z0-9._~-]{8,512}$/;

/** httpOnly so client code never holds the token; one day, like the link it replaces. */
export function sessionCookieOptions(secure = process.env.COOKIE_SECURE === "true") {
  return { httpOnly: true, sameSite: "lax", secure, path: "/", maxAge: 60 * 60 * 24 } as const;
}
