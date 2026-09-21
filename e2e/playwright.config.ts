import { defineConfig, devices } from "@playwright/test";

/**
 * Two projects:
 * - `local`: the whole customer and agent flow against the docker compose stack (mock externals and LLM, seed
 *   customers A–D). The frontend must run with AGENT_DEV_AUTH=true, which compose sets.
 * - `dev-smoke`: read-only checks of the deployed develop hosts; nothing there needs a login.
 * - `dev-perf`: the page-load SLA of the develop hosts (run with --workers=1; see tests/perf).
 *
 * E2E_HOST_RESOLVER_RULES passes Chromium's --host-resolver-rules, e.g. to pin a new hostname to the ALB before
 * local DNS knows it: "MAP dev.app.onboardassist.click 3.38.86.215".
 */
const CI = !!process.env.CI;

export default defineConfig({
  timeout: 90_000,
  expect: { timeout: 20_000 }, // a graph step can take a few seconds
  fullyParallel: true,
  workers: CI ? 2 : 4,
  retries: CI ? 1 : 0,
  forbidOnly: CI,
  reporter: CI ? [["list"], ["html", { open: "never" }], ["github"]] : [["list"], ["html", { open: "never" }]],
  use: {
    launchOptions: process.env.E2E_HOST_RESOLVER_RULES
      ? { args: [`--host-resolver-rules=${process.env.E2E_HOST_RESOLVER_RULES}`] }
      : {},
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "local",
      testDir: "tests/local",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: process.env.E2E_BASE_URL ?? "http://localhost:13000",
      },
    },
    {
      name: "dev-smoke",
      testDir: "tests/smoke",
      retries: 2,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "dev-perf",
      testDir: "tests/perf",
      retries: 0, // a budget miss is the signal; retrying would hide it
      use: { ...devices["Desktop Chrome"], trace: "off", video: "off" },
    },
  ],
});
