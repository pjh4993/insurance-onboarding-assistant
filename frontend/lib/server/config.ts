import "server-only";

export const SESSION_COOKIE = "onb_session";

export function backendUrl(): string {
  return (process.env.BACKEND_URL ?? "http://localhost:18000").replace(/\/+$/, "");
}

export function cookieSecure(): boolean {
  return process.env.COOKIE_SECURE === "true";
}
