import "server-only";

/**
 * Resolve the calling agent's id for X-Agent-Id.
 *
 * - AGENT_DEV_AUTH=true: every caller is "agent-demo" (local and develop only).
 * - Otherwise: HOOK for real auth. Behind an ALB with OIDC/Cognito the load balancer injects
 *   `x-amzn-oidc-identity` (the user's `sub`) and a signed `x-amzn-oidc-data` JWT. Production must verify
 *   that JWT's signature against the ALB public key before trusting the identity; until that is wired,
 *   non-dev mode only accepts the identity header and returns null (401) without it.
 */
export function resolveAgentId(headers: Headers): string | null {
  if (process.env.AGENT_DEV_AUTH === "true") return "agent-demo";
  // TODO(auth): verify x-amzn-oidc-data (ES256, key from https://public-keys.auth.elb.<region>.amazonaws.com/<kid>).
  const oidcIdentity = headers.get("x-amzn-oidc-identity");
  return oidcIdentity && oidcIdentity.trim() ? oidcIdentity.trim() : null;
}
