import { exportJWK, generateKeyPair, SignJWT, createLocalJWKSet, type JWTPayload } from "jose";
import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

const { operatorFromClaims, verifyOperatorToken, issuerOf } = await import("./operatorAuth");

const config = { region: "ap-northeast-2", userPoolId: "ap-northeast-2_abc", clientId: "operator-client" };

async function keys() {
  const { publicKey, privateKey } = await generateKeyPair("RS256");
  const jwk = { ...(await exportJWK(publicKey)), kid: "k1", alg: "RS256" };
  return { privateKey, jwks: createLocalJWKSet({ keys: [jwk] }) };
}

async function token(privateKey: CryptoKey, claims: JWTPayload, opts: { issuer?: string; expires?: string } = {}) {
  return new SignJWT(claims)
    .setProtectedHeader({ alg: "RS256", kid: "k1" })
    .setIssuer(opts.issuer ?? issuerOf(config))
    .setIssuedAt()
    .setExpirationTime(opts.expires ?? "5m")
    .sign(privateKey);
}

const operatorClaims = {
  token_use: "access",
  client_id: "operator-client",
  username: "kim.operator",
  "cognito:groups": ["agents", "operators"],
};

describe("operatorFromClaims", () => {
  it("accepts an access token of the console's client in the operators group", () => {
    expect(operatorFromClaims(operatorClaims, "operator-client")).toEqual({ id: "kim.operator" });
  });
  it("refuses anyone else", () => {
    expect(operatorFromClaims({ ...operatorClaims, "cognito:groups": ["agents"] }, "operator-client")).toBeNull();
    expect(operatorFromClaims({ ...operatorClaims, client_id: "agent-client" }, "operator-client")).toBeNull();
    expect(operatorFromClaims({ ...operatorClaims, token_use: "id" }, "operator-client")).toBeNull();
  });
});

describe("verifyOperatorToken", () => {
  it("verifies the signature, issuer and expiry before trusting the claims", async () => {
    const { privateKey, jwks } = await keys();
    expect(await verifyOperatorToken(await token(privateKey, operatorClaims), config, jwks)).toEqual({
      id: "kim.operator",
    });

    const other = await keys();
    expect(await verifyOperatorToken(await token(other.privateKey, operatorClaims), config, jwks)).toBeNull();
    const wrongIssuer = await token(privateKey, operatorClaims, { issuer: "https://evil.example" });
    expect(await verifyOperatorToken(wrongIssuer, config, jwks)).toBeNull();
    const expired = await token(privateKey, operatorClaims, { expires: "-1m" });
    expect(await verifyOperatorToken(expired, config, jwks)).toBeNull();
    expect(await verifyOperatorToken("not-a-jwt", config, jwks)).toBeNull();
  });
});
