import { describe, expect, it } from "vitest";
import { agentConsoleHref, baseUrl, customerLink, isAgentHost } from "./hosts";

const AGENT = "https://dev.agent.onboardassist.click";
const APP = "https://dev.app.onboardassist.click";

describe("baseUrl", () => {
  it("normalizes to an origin", () => {
    expect(baseUrl(AGENT)).toBe(AGENT);
    expect(baseUrl(`${AGENT}/`)).toBe(AGENT);
    expect(baseUrl(` ${APP}/some/path `)).toBe(APP);
    expect(baseUrl("http://localhost:13000")).toBe("http://localhost:13000");
  });

  it("is null when unset or not an http(s) URL", () => {
    expect(baseUrl(undefined)).toBeNull();
    expect(baseUrl("")).toBeNull();
    expect(baseUrl("  ")).toBeNull();
    expect(baseUrl("dev.agent.onboardassist.click")).toBeNull();
    expect(baseUrl("ftp://dev.agent.onboardassist.click")).toBeNull();
  });
});

describe("isAgentHost", () => {
  it("matches the agent host, ignoring case", () => {
    expect(isAgentHost("dev.agent.onboardassist.click", AGENT)).toBe(true);
    expect(isAgentHost("DEV.Agent.onboardassist.click", AGENT)).toBe(true);
  });

  it("does not match other hosts or ports", () => {
    expect(isAgentHost("dev.app.onboardassist.click", AGENT)).toBe(false);
    expect(isAgentHost("dev.agent.onboardassist.click:8443", AGENT)).toBe(false);
    expect(isAgentHost("localhost:13000", "http://localhost:13000")).toBe(true);
  });

  it("never matches without a host or an agent base", () => {
    expect(isAgentHost("dev.agent.onboardassist.click", null)).toBe(false);
    expect(isAgentHost(null, AGENT)).toBe(false);
  });
});

describe("links across hosts", () => {
  it("points For agents at the agent host's root, else /agent", () => {
    expect(agentConsoleHref(AGENT)).toBe(`${AGENT}/`);
    expect(agentConsoleHref(null)).toBe("/agent");
  });

  it("builds customer links on the customer host, else the current origin", () => {
    expect(customerLink(APP, AGENT, "/s/tok123")).toBe(`${APP}/s/tok123`);
    expect(customerLink(null, "http://localhost:13000", "/s/tok123")).toBe("http://localhost:13000/s/tok123");
    expect(customerLink(null, "http://localhost:13000/", "/s/tok123")).toBe("http://localhost:13000/s/tok123");
  });
});
