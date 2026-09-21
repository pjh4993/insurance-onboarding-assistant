// Split hostnames (unit-tested): the customer app and the agent console can live on separate hosts, set by
// the server-side env vars CUSTOMER_BASE_URL and AGENT_BASE_URL. Unset, everything is served from one host
// (/ for customers, /agent for agents), which is how it runs locally. No "server-only": proxy.ts loads this.

/** An env value as a bare origin ("https://x.example"), or null when unset or not an http(s) URL. */
export function baseUrl(value: string | null | undefined): string | null {
  if (!value?.trim()) return null;
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:" ? url.origin : null;
  } catch {
    return null;
  }
}

/** Whether a request's Host header names the host of `base`. Always false when that host is not set. */
export function isHost(host: string | null | undefined, base: string | null): boolean {
  if (!host || !base) return false;
  return host.trim().toLowerCase() === new URL(base).host;
}

/** Whether a request's Host header names the agent host. Always false when no agent host is set. */
export function isAgentHost(host: string | null | undefined, agentBase: string | null): boolean {
  return isHost(host, agentBase);
}

/** Whether a request's Host header names the operator host. Always false when no operator host is set. */
export function isOperatorHost(host: string | null | undefined, operatorBase: string | null): boolean {
  return isHost(host, operatorBase);
}

/** Where the landing's "For agents" link goes: the agent host's root (the console), else /agent. */
export function agentConsoleHref(agentBase: string | null): string {
  return agentBase ? `${agentBase}/` : "/agent";
}

/** A customer link for a backend customer_path ("/s/{token}"): on the customer host when set, else here. */
export function customerLink(customerBase: string | null, currentOrigin: string, customerPath: string): string {
  return `${customerBase ?? currentOrigin.replace(/\/+$/, "")}${customerPath}`;
}

/**
 * Where an agent path requested outside the agent host should go: the same page on the agent host, with no
 * port in the URL (the ALB's own redirect action always writes one). /agent is the agent host's root there.
 * Null when there is no agent host, the request is already on it, or the path is not an agent page.
 */
export function agentHostRedirect(
  pathname: string,
  search: string,
  host: string | null | undefined,
  agentBase: string | null,
): string | null {
  return hostRedirect("/agent", pathname, search, host, agentBase);
}

/** The same for operator pages (/operator), which belong on the operator host. */
export function operatorHostRedirect(
  pathname: string,
  search: string,
  host: string | null | undefined,
  operatorBase: string | null,
): string | null {
  return hostRedirect("/operator", pathname, search, host, operatorBase);
}

function hostRedirect(
  prefix: string,
  pathname: string,
  search: string,
  host: string | null | undefined,
  base: string | null,
): string | null {
  if (!base || isHost(host, base)) return null;
  if (pathname !== prefix && !pathname.startsWith(`${prefix}/`)) return null;
  return `${base}${pathname === prefix ? "/" : pathname}${search}`;
}
