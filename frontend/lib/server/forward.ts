import "server-only";
import { backendUrl } from "./config";

// Hop-by-hop and encoding headers that must not be copied from the upstream response.
const DROP = new Set(["connection", "keep-alive", "transfer-encoding", "content-encoding", "content-length"]);

export function jsonError(status: number, error: string): Response {
  return Response.json({ error }, { status });
}

/**
 * Forward a request to the backend and stream the upstream body back unchanged.
 * Works for JSON and for SSE: the body is piped, never buffered, and the upstream fetch is aborted
 * when the browser disconnects.
 */
export async function forward(
  req: Request,
  path: string,
  headers: Record<string, string>,
  opts: { method?: string; sse?: boolean } = {},
): Promise<Response> {
  const method = opts.method ?? req.method;
  const outHeaders = new Headers(headers);
  outHeaders.set("Accept", opts.sse ? "text/event-stream" : "application/json");
  let body: string | undefined;
  if (method !== "GET" && method !== "HEAD") {
    body = await req.text();
    outHeaders.set("Content-Type", "application/json");
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}${path}`, {
      method,
      headers: outHeaders,
      body: body || undefined,
      cache: "no-store",
      signal: req.signal,
      redirect: "manual",
    });
  } catch (err) {
    if (req.signal.aborted) return new Response(null, { status: 499 });
    console.error(`[proxy] ${method} ${path} failed:`, err);
    return jsonError(502, "Backend unavailable");
  }

  const resHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!DROP.has(key.toLowerCase())) resHeaders.set(key, value);
  });
  if (opts.sse) {
    resHeaders.set("Content-Type", "text/event-stream; charset=utf-8");
    resHeaders.set("Cache-Control", "no-cache, no-transform");
    resHeaders.set("X-Accel-Buffering", "no");
  } else {
    resHeaders.set("Cache-Control", "no-store");
  }
  return new Response(upstream.body, { status: upstream.status, headers: resHeaders });
}
