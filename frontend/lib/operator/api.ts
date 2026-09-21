// Browser-side client for the operator console: every call goes to this app's /api/operator/* handlers, which
// verify the operator and relay to the backend.
import type { Outline } from "./refs";
import type { Bump, ConfigStatus, PublishResult, ValidateResult, VersionDetail, VersionItem } from "./types";

export class OperatorApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Every problem the backend found in a bundle, when it rejected one. */
    public problems: string[] = [],
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let message = res.statusText || `HTTP ${res.status}`;
    let problems: string[] = [];
    try {
      const body = (await res.json()) as { detail?: unknown; error?: unknown };
      const detail = body.detail ?? body.error;
      if (detail && typeof detail === "object" && "message" in detail) {
        const d = detail as { message: unknown; problems?: unknown };
        message = String(d.message);
        if (Array.isArray(d.problems)) problems = d.problems.map(String);
      } else if (detail !== undefined) {
        message = String(detail);
      }
    } catch {
      /* non-JSON error body */
    }
    throw new OperatorApiError(res.status, message, problems);
  }
  return (await res.json()) as T;
}

export const operatorApi = {
  me: () => call<{ operator_id: string }>("/api/operator/me"),
  status: () => call<ConfigStatus>("/api/operator/config"),
  graph: () => call<Outline>("/api/operator/graph"),
  versions: () => call<{ versions: VersionItem[] }>("/api/operator/config/versions").then((r) => r.versions),
  version: (v: string) => call<VersionDetail>(`/api/operator/config/versions/${encodeURIComponent(v)}`),
  validate: (files: Record<string, string>) =>
    call<ValidateResult>("/api/operator/config/validate", { method: "POST", body: JSON.stringify({ files }) }),
  publish: (files: Record<string, string>, notes: string, bump: Bump) =>
    call<PublishResult>("/api/operator/config/versions", {
      method: "POST",
      body: JSON.stringify({ files, notes, bump }),
    }),
  restart: () => call<{ restarting: boolean }>("/api/operator/restart", { method: "POST" }),
};
