// Typed browser-side client. Every call goes to this Next.js app's /api/* route handlers,
// which proxy to BACKEND_URL; the browser never talks to the backend directly.
import type {
  CreateSessionResponse,
  InputBody,
  Locale,
  Market,
  SessionDetail,
  SessionSummary,
  SessionView,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Seconds to wait, on a 429 from /api/start. */
    public retryAfter: number | null = null,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    let retryAfter: number | null = null;
    try {
      const body = (await res.json()) as { detail?: unknown; error?: unknown; retry_after?: unknown };
      detail = String(body.detail ?? body.error ?? detail);
      if (typeof body.retry_after === "number") retryAfter = body.retry_after;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail || `HTTP ${res.status}`, retryAfter);
  }
  return (await res.json()) as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const put = <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) });

/** The public landing page: start a self-serve session. The session cookie is set by the response. */
export const publicApi = {
  start: (market: Market, locale: Locale) => post<{ session_id: string }>("/api/start", { market, locale }),
};

export const customerApi = {
  getSession: () => request<SessionView>("/api/customer/session"),
  sendInput: (body: InputBody) => post<{ accepted: boolean }>("/api/customer/session/input", body),
  setLocale: (locale: Locale) => put<SessionSummary>("/api/customer/session/locale", { locale }),
  streamUrl: "/api/customer/session/stream",
};

export const agentApi = {
  me: () => request<{ agent_id: string }>("/api/agent/me"),
  createSession: (market: Market, locale?: Locale) =>
    post<CreateSessionResponse>("/api/agent/sessions", locale ? { market, locale } : { market }),
  listSessions: () => request<{ sessions: SessionSummary[] }>("/api/agent/sessions"),
  getSession: (id: string) => request<SessionDetail>(`/api/agent/sessions/${encodeURIComponent(id)}`),
  assign: (id: string) => post<SessionSummary>(`/api/agent/sessions/${encodeURIComponent(id)}/assign`),
  sendInput: (id: string, body: InputBody) =>
    post<{ accepted: boolean }>(`/api/agent/sessions/${encodeURIComponent(id)}/input`, body),
  setLocale: (id: string, locale: Locale) =>
    put<SessionSummary>(`/api/agent/sessions/${encodeURIComponent(id)}/locale`, { locale }),
  streamUrl: "/api/agent/stream",
  sessionStreamUrl: (id: string) => `/api/agent/sessions/${encodeURIComponent(id)}/stream`,
};
