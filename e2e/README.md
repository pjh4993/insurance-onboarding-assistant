# e2e

Browser tests for the customer app and the agent console, plus the checklist for exploratory QA.
The full description, including the page-load SLA, is in [docs/guides/development.md](../docs/guides/development.md#browser-tests-e2e).

```bash
make e2e-setup          # once: dependencies, Playwright's Chromium, agent-browser's Chrome
make e2e                # `local`: flows against the compose stack (E2E_BASE_URL, default http://localhost:13000)
make e2e-dev            # `dev-smoke` and `dev-perf` against the develop hosts (DEV_APP_URL, DEV_AGENT_URL, DEV_DOCS_URL)
pnpm --dir e2e report   # open the last HTML report
```

| Path | What |
|---|---|
| `tests/local/` | landing, public landing, seed customers A–D, agent console |
| `tests/smoke/` | read-only checks of the develop hosts |
| `tests/perf/` | page-load SLA (p75 of `PERF_RUNS` cold loads, default 8) |
| `support/` | UI strings from `frontend/messages`, seed customers, the customer-app driver, API setup, load metrics |
| `agent-qa/checklist.md` | what the `frontend-qa` skill walks through with agent-browser |

- The `local` project creates sessions through the frontend's `/api/agent/sessions`, which needs
  `AGENT_DEV_AUTH=true` (compose sets it). The public landing test starts one self-serve session; the backend
  allows five per IP per hour, so repeated runs within the hour can hit the limit on a long-lived stack.
- A new hostname can lag in local DNS. `E2E_HOST_RESOLVER_RULES="MAP dev.app.onboardassist.click <alb-ip>"` pins it
  in Chromium.
