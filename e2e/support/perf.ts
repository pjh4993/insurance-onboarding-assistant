// Page-load measurement for the landing SLA: each sample is a fresh browser context (cold cache), and the
// budget applies to the 75th percentile of the samples.
import type { Browser } from "@playwright/test";

export type Sample = { ttfb: number; fcp: number; lcp: number; cls: number; load: number };
export type Metric = keyof Sample;

export async function sample(browser: Browser, url: string): Promise<Sample> {
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    await page.addInitScript(() => {
      const w = window as unknown as { __lcp: number; __cls: number };
      w.__lcp = 0;
      w.__cls = 0;
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) w.__lcp = e.startTime;
      }).observe({ type: "largest-contentful-paint", buffered: true });
      new PerformanceObserver((list) => {
        for (const e of list.getEntries() as (PerformanceEntry & { value: number; hadRecentInput: boolean })[])
          if (!e.hadRecentInput) w.__cls += e.value;
      }).observe({ type: "layout-shift", buffered: true });
    });
    await page.goto(url, { waitUntil: "load" });
    await page.waitForTimeout(1_000); // let LCP and late layout shifts settle
    return await page.evaluate(() => {
      const w = window as unknown as { __lcp: number; __cls: number };
      const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming;
      const fcp = performance.getEntriesByName("first-contentful-paint")[0];
      return {
        ttfb: nav.responseStart,
        fcp: fcp ? fcp.startTime : Number.NaN,
        lcp: w.__lcp,
        cls: w.__cls,
        load: nav.loadEventEnd,
      };
    });
  } finally {
    await context.close();
  }
}

export function p75(values: number[]): number {
  const sorted = values.filter((v) => !Number.isNaN(v)).sort((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil(0.75 * sorted.length) - 1)];
}
