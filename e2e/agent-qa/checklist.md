# Exploratory QA checklist

Paths the Playwright suite does not replay. Tick what you covered in the report; add items when a finding shows a
gap. The seed customers and what the mock does for each are in `docs/guides/demo.md`.

## Public landing (`/`)

- [ ] Market (KR/US) and language (한국어/English) switch independently; product cards follow the market, copy
      follows the language.
- [ ] Each product card and the free-text box start a session and land on `/chat`; the chosen product or the typed
      text is pre-filled as the first needs answer after identity.
- [ ] Coming back to `/` with an unfinished session offers to continue it; starting a new one works.
- [ ] A sixth start within an hour shows the rate-limit notice (develop only, and only if the question needs it).

## Customer chat (`/chat`, `/s/{token}`)

- [ ] Identity form: empty and malformed fields (email, phone) are rejected before sending; the consent box is
      optional.
- [ ] Wrong OTP, then the document check (seed C); two failures hand off (seed D) and the page says an agent is
      coming.
- [ ] Answer faster than the assistant: type and send the moment a reply appears. Input must stay disabled until
      the turn ends, with no "still processing" error.
- [ ] Switch the language mid-chat: earlier messages stay, the next reply and every control follow the new language.
- [ ] Recommendation cards: accept, change my answers, decline all (with and without a reason).
- [ ] Confirm summary: "fix something" goes back to the right question.
- [ ] Reload at every step: the chat resumes where it was, no duplicate messages.
- [ ] Drop the connection (devtools offline, or stop the backend): the reconnecting badge shows and clears.
- [ ] An expired or made-up `/s/…` link shows the expired notice and a way home.
- [ ] Mobile (`set device "iPhone 14"`): no horizontal scroll, the composer stays above the keyboard area, cards and
      forms fit.
- [ ] Keyboard only: every control is reachable with Tab and has a visible focus ring; Enter sends, Shift+Enter
      makes a new line, Korean IME composition does not send early.

## Agent console (`/agent`)

- [ ] New session for each market and language; the link opens the right landing.
- [ ] Session list: a handoff jumps to the top; badges (stage, waits, market, language) match the customer page.
- [ ] Assign, then resolve a handoff with Verified, Continue and End; the customer page follows each over SSE.
- [ ] Answer on the customer's behalf in ASSIST mode; the customer sees the agent's message.
- [ ] Change the session language from the detail panel; the customer page switches.
- [ ] The console's own language switch does not change any session's language.

## Everywhere

- [ ] `ab console` and `ab errors` are empty apart from known extension noise.
- [ ] No request to the backend's host from the browser: everything goes through the frontend's `/api/*`.
- [ ] Page titles and `<html lang>` follow the language shown.
