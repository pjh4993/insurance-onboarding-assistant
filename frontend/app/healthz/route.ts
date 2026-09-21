import { forward } from "@/lib/server/forward";

export const dynamic = "force-dynamic";

// Deploy smoke test: the public URL's /healthz reaches the frontend, which checks the backend behind it.
// Returns the backend's {"status":"ok"}, or 502 when the backend is down.
// (/api/healthz is the frontend-only liveness check used by the container HEALTHCHECK and the ALB.)
export function GET(req: Request) {
  return forward(req, "/healthz", {});
}
