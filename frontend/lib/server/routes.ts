import "server-only";
import { cookies } from "next/headers";
import { resolveAgentId } from "./agentAuth";
import { resolveOperator } from "./operatorAuth";
import { SESSION_COOKIE } from "./config";
import { forward, jsonError } from "./forward";

/** Forward as the customer: X-Session-Token from the httpOnly cookie set on /s/{token}. */
export async function forwardCustomer(req: Request, path: string, opts?: { sse?: boolean }) {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return jsonError(401, "No session. Open your session link again.");
  return forward(req, path, { "X-Session-Token": token }, opts);
}

/** Forward as an agent: X-Agent-Id from the auth hook. */
export async function forwardAgent(req: Request, path: string, opts?: { sse?: boolean }) {
  const agentId = resolveAgentId(req.headers);
  if (!agentId) return jsonError(401, "Agent sign-in required");
  return forward(req, path, { "X-Agent-Id": agentId }, opts);
}

/** Forward as an operator: X-Operator-Id once the operator's Cognito login is verified. */
export async function forwardOperator(req: Request, path: string) {
  const operator = await resolveOperator(req.headers);
  if (!operator) return jsonError(401, "Operator sign-in required");
  return forward(req, path, { "X-Operator-Id": operator.id });
}
