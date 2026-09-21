import "server-only";
import { createRemoteJWKSet, jwtVerify, type JWTPayload, type JWTVerifyGetKey } from "jose";

/**
 * Resolve the calling operator for X-Operator-Id.
 *
 * Operators change what the agent says to every customer, so their login is verified, not trusted:
 * - OPERATOR_DEV_AUTH=true: every caller is "operator-demo" (local only).
 * - Otherwise the ALB, after the Cognito login on the operator host, forwards the user's Cognito access token
 *   in `x-amzn-oidc-accesstoken`. It is verified against the user pool's published keys (RS256), and must be an
 *   access token of the operator console's app client whose `cognito:groups` include "operators". A request
 *   that reached the frontend any other way cannot forge one.
 */
export const OPERATORS_GROUP = "operators";

export type Operator = { id: string };

export type CognitoConfig = { region: string; userPoolId: string; clientId: string };

export function cognitoConfig(env: NodeJS.ProcessEnv = process.env): CognitoConfig | null {
  const region = env.COGNITO_REGION?.trim();
  const userPoolId = env.COGNITO_USER_POOL_ID?.trim();
  const clientId = env.COGNITO_OPERATOR_CLIENT_ID?.trim();
  return region && userPoolId && clientId ? { region, userPoolId, clientId } : null;
}

export function issuerOf(config: CognitoConfig): string {
  return `https://cognito-idp.${config.region}.amazonaws.com/${config.userPoolId}`;
}

const keySets = new Map<string, JWTVerifyGetKey>();

function keysFor(issuer: string): JWTVerifyGetKey {
  let keys = keySets.get(issuer);
  if (!keys) {
    keys = createRemoteJWKSet(new URL(`${issuer}/.well-known/jwks.json`));
    keySets.set(issuer, keys);
  }
  return keys;
}

/** The operator an access token's claims name, or null when they are not an operator of this console. */
export function operatorFromClaims(claims: JWTPayload, clientId: string): Operator | null {
  if (claims.token_use !== "access" || claims.client_id !== clientId) return null;
  const groups = claims["cognito:groups"];
  if (!Array.isArray(groups) || !groups.includes(OPERATORS_GROUP)) return null;
  const id = typeof claims.username === "string" && claims.username ? claims.username : claims.sub;
  return id ? { id } : null;
}

/** Verify a Cognito access token and return the operator it names, or null. */
export async function verifyOperatorToken(
  token: string,
  config: CognitoConfig,
  keys: JWTVerifyGetKey = keysFor(issuerOf(config)),
): Promise<Operator | null> {
  try {
    const { payload } = await jwtVerify(token, keys, { issuer: issuerOf(config), algorithms: ["RS256"] });
    return operatorFromClaims(payload, config.clientId);
  } catch {
    return null;
  }
}

export async function resolveOperator(headers: Headers): Promise<Operator | null> {
  if (process.env.OPERATOR_DEV_AUTH === "true") return { id: "operator-demo" };
  const token = headers.get("x-amzn-oidc-accesstoken")?.trim();
  const config = cognitoConfig();
  if (!token || !config) return null;
  return verifyOperatorToken(token, config);
}
