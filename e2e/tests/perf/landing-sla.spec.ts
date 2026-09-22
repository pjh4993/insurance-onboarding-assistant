// Page-load SLA for develop: p75 over cold loads, desktop Chrome. The budgets are several times what develop
// measured from Seoul (2026-09-22: landing LCP p75 0.3 s), so a run from a US CI runner still passes and a
// real slowdown does not. TTFB is the server's time (request sent to first byte), so it leaves out connection
// setup, several round trips from a US runner.
import { expect, test } from "@playwright/test";
import { DEV } from "../../support/hosts";
import { p75, sample, type Metric, type Sample } from "../../support/perf";

const RUNS = Number(process.env.PERF_RUNS ?? 8);

type Budget = Partial<Record<Metric, number>>;
const PAGES: { name: string; url: string; budget: Budget }[] = [
  { name: "customer landing", url: `${DEV.app}/`, budget: { ttfb: 600, lcp: 1_500, cls: 0.1 } },
  { name: "docs home", url: `${DEV.docs}/`, budget: { ttfb: 600, lcp: 2_000, cls: 0.1 } },
  {
    name: "docs page",
    url: `${DEV.docs}/design/01-solution-architecture/`,
    budget: { ttfb: 600, lcp: 2_000, cls: 0.1 },
  },
  // Ends on Cognito's hosted login page, so only the whole load is ours to budget.
  { name: "agent login redirect", url: `${DEV.agent}/agent`, budget: { load: 2_000 } },
];

test.describe.configure({ mode: "serial" }); // samples must not compete with each other

for (const { name, url, budget } of PAGES) {
  test(`${name} meets its load budget`, async ({ browser }, testInfo) => {
    test.setTimeout(RUNS * 20_000);
    const samples: Sample[] = [];
    for (let i = 0; i < RUNS; i++) samples.push(await sample(browser, url));

    const result = Object.fromEntries(
      (Object.keys(samples[0]) as Metric[]).map((m) => [m, Math.round(p75(samples.map((s) => s[m])) * 1000) / 1000]),
    );
    await testInfo.attach("p75.json", { body: JSON.stringify({ url, runs: RUNS, p75: result, budget, samples }, null, 2), contentType: "application/json" });
    console.log(`${name}: p75 ${JSON.stringify(result)}`);

    for (const [metric, limit] of Object.entries(budget) as [Metric, number][]) {
      expect.soft(result[metric], `${name} ${metric} p75`).toBeLessThanOrEqual(limit);
    }
  });
}
