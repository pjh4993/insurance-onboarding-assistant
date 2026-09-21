import { afterEach, describe, expect, it, vi } from "vitest";
import { SESSION_TOKEN_RE, sessionCookieOptions } from "./sessionCookie";

describe("session cookie", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("is httpOnly, lax, site-wide and lasts a day", () => {
    expect(sessionCookieOptions(false)).toEqual({ httpOnly: true, sameSite: "lax", secure: false, path: "/", maxAge: 86400 });
  });

  it("is secure only when COOKIE_SECURE=true", () => {
    vi.stubEnv("COOKIE_SECURE", "true");
    expect(sessionCookieOptions().secure).toBe(true);
    vi.stubEnv("COOKIE_SECURE", "1");
    expect(sessionCookieOptions().secure).toBe(false);
  });

  it("accepts only token-shaped values", () => {
    expect(SESSION_TOKEN_RE.test("abcDEF12-_.~")).toBe(true);
    expect(SESSION_TOKEN_RE.test("short")).toBe(false);
    expect(SESSION_TOKEN_RE.test("has space in it")).toBe(false);
  });
});
