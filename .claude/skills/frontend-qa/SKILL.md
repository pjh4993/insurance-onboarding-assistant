---
name: frontend-qa
description: Exploratory QA of the customer app and agent console with agent-browser (Vercel Labs' browser CLI for agents). Use when asked to QA, poke at, or look for bugs in the frontend, locally or on develop, or to check a UI change the way a person would; it complements the Playwright suite in e2e/, which only replays fixed scenarios.
---

# Frontend exploratory QA with agent-browser

Playwright (`e2e/`) checks that known paths still work. This skill is for finding what nobody wrote a test for:
walk the app like a customer or an agent, try the odd paths in `e2e/agent-qa/checklist.md`, and report what breaks.

## Setup (once)

From the repo root:

```bash
pnpm --dir e2e install
pnpm --dir e2e exec agent-browser install   # downloads Chrome for Testing
```

Run the CLI as `pnpm --dir e2e exec agent-browser <command>`; below it is written `ab`.

## Targets

| Target | App | Agent console | How a customer gets in |
|---|---|---|---|
| Local (`docker compose up --build`) | http://localhost:13000 | http://localhost:13000/agent (signed in as `agent-demo`) | `/` (self-serve), or a link: `curl -s -X POST localhost:13000/api/agent/sessions -H 'Content-Type: application/json' -d '{"market":"KR"}'` → `customer_path` |
| develop | https://dev.app.onboardassist.click | https://dev.agent.onboardassist.click (Cognito; a person must log in) | `/` only |

- Prefer local: the mock makes every seed customer end the same way (`docs/guides/demo.md`). Enter the seed customers
  from `contracts/seed-customers.json`, never real personal data.
- On develop, self-serve starts are limited to five per IP per hour, and every start leaves a session in the develop
  database. Start as few as the question needs.
- Use one `--session <name>` per role (`customer`, `agent`) so their cookies stay apart.

## Loop

1. `ab --session customer open <url>`, then `ab set viewport 1280 800` (desktop) or `ab set device "iPhone 14"`.
2. `ab snapshot -i` for the interactive elements and their refs; act with `ab click @e3`, `ab fill @e5 "…"`,
   `ab select @e7 PASSPORT`, `ab press Enter`.
3. After each action wait for the state you expect (`ab wait --text "…"`), not for `networkidle`: the chat keeps an
   SSE stream open, so the network never goes quiet.
4. Look, don't guess: `ab screenshot --annotate <file>` when layout matters; `ab console` and `ab errors` after
   every screen; `ab network requests --status 400-599` when something fails.
5. Take a fresh snapshot after anything changes the page; refs from an old snapshot go stale.

## What to check

Work through `e2e/agent-qa/checklist.md`, in the order that fits the question. When the question is about one
change, start from the screens it touches, then do the rest of that area.

## Report

Write `e2e/qa-reports/<yyyy-mm-dd>-<topic>.md` (git-ignored) with screenshots saved next to it:

- **Scope**: target, commit (`git rev-parse --short HEAD`), viewport(s), locale(s).
- **Findings**, most severe first. Each one has the steps to reproduce, expected against actual, a screenshot, and
  any console error or failed request. Say whether it reproduces every time.
- **Checked and fine**: the checklist items you covered without findings, so the next run knows what was done.

Then summarise the findings for the user and offer to turn each reproducible one into a Playwright test in
`e2e/tests/local/`.
