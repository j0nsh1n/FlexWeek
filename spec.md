# spec.md — FlexWeek

## Problem
Students plan by guilt, not by constraints: a to-do list has no idea that school
runs 08:00–14:30, practice takes the evening, and a three-hour paper is due
tomorrow. FlexWeek takes a student's fixed week (school, sport, commute, sleep)
plus their assignments, places the assignments in the gaps with a constraint
solver, and explains in plain English every time something could not be placed
or had to move. Built as a Congressional App Challenge 2026 entry. Working title
was *Reslot*; the public name is **FlexWeek**.

## Intended Users
High-school students using individual accounts through the web app and a planned
separate desktop app. New accounts start with an empty week; no anonymous demo
mode or sample-data fallback. Secondary audience: CAC judges, who create an
account and can inspect the GitHub repository.

Scope revision approved 2026-09-06: accounts, shared persistence, Daily Scheduler
Nocturne/Slate themes first; separate desktop delivery and calendar interaction
parity next. Visual redesign and audits are deferred. The previous Oct 3 feature
freeze is superseded by the expanded roadmap.

## Required Behavior
Contract for the finished app:

- A week is a set of `TimeBlock`s: `locked` blocks have a fixed `start`;
  `flexible` blocks have a `duration_min` and a deadline (`latest`) and are
  placed by the solver.
- The solver places every flexible block on the 15-minute grid (Mon–Sun,
  06:00–23:00) without overlapping any locked block or any other placed block.
- Search order respects priority (1 = test, 2 = quiz, 3 = homework,
  4 = reading); a higher-priority block wins a contested slot.
- Energy windows (`high` / `medium` / `low`) are a soft preference on value
  order, never a hard constraint.
- Every unplaced block and every move carries a machine reason code, rendered as
  a plain-English sentence: `LOCKED_OVERLAP`, `DEADLINE_MISS`, `NO_SLOT_LEFT`,
  `PRIORITY_PREEMPT`, `ENERGY_MISMATCH` (soft), `SLEEP_GUARD`,
  `RESHUFFLE_AFTER_MISS`.
- Sleep (23:00–06:00) is a guard the solver never places into and never steals.
- Solving is capped at 150 ms. On timeout the app returns the best partial
  placement plus reasons for what is unplaced — it never hangs and never
  returns nothing.
- Edge cases: an unsolvable week returns `complete: false` with reasons rather
  than an error; a duration that is not a positive multiple of 15 is rejected in
  both the browser form and the API. Legacy browser data is explicitly imported
  into a signed-in account; invalid data stays untouched and never loads a demo.

Conditional (Week 5, only if the must-ship set is green on Oct 4):
- Cascade: marking a locked block as missed re-solves the remaining flexible
  blocks and lists the resulting diffs as moves.
- Deadline slack shown as ok / tight / danger badges.

## User Experience
Web app, one page, desktop-first (designed at 1280px) and usable on a phone at
390px. Vanilla JavaScript, HTML5 and CSS — **no npm, no build step, no
framework**. FastAPI serves `frontend/` as static files, so there is one origin
and no CORS.

Run locally:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --reload    # then open http://127.0.0.1:8000/
```

Current account/API contract:

| Method | Path | Behavior |
|---|---|---|
| POST | `/api/auth/register` | Create username/password account and session |
| POST | `/api/auth/login` | Authenticate and rotate session |
| POST | `/api/auth/logout` | Revoke current session |
| GET | `/api/auth/me` | Current account; 401 when absent/expired |
| GET/PUT | `/api/week` | Own current week with revision-checked saves |
| GET/PUT | `/api/preferences` | Own Nocturne/Slate theme |
| POST | `/api/solve` | Authenticated week in, SolveTrace out; no storage mutation |
| GET | `/api/health` | Public health response |

The solve trace contains `placed`, `unplaced`, `moves`, `failed_constraints`,
`solve_ms`, `complete`. Demo endpoints are removed. Test-only seed JSON remains.
Writes require `X-FlexWeek-Request: 1`; browser origins must match
`FLEXWEEK_ORIGIN`. Clients send `X-FlexWeek-Account` to reject requests after a
cross-tab account change. No CORS is enabled.

Registration: normalized case-insensitive ASCII username (3–32 letters, digits,
underscores), password 12–128 characters. New accounts have an empty week and
Nocturne theme. Duplicate usernames return 409, invalid input 422, expired or
missing sessions 401, stale changed writes 409, throttled auth 429, oversized
requests 413, transient database failures 503. Identical week retries return
success without duplicate blocks or another revision increment.

One current week per account initially; dated multiple weeks are a later
migration. A week has at most 100 uniquely identified blocks; titles 1–80,
course names at most 40, durations positive multiples of 15 up to 7140 minutes,
and unique day indices. Explicit starts are on the visible grid and end by
23:00. Deadlines/earliest bounds use full English weekday plus HH:MM, or HH:MM.
API write bodies are capped at 256 KiB.

## Architecture
- Language/runtime: **Python 3.14** — PINNED. Verified against the local
  interpreter (3.14.7) and `Github Templates/ci.yml` (`python-version: "3.14"`).
  Never downgrade.
- Current languages: Python, JavaScript, HTML5, CSS, and SQL for account storage.
  Desktop-shell selection is deferred to the packaging slice.
- Frameworks, pinned in `requirements.txt`: FastAPI 0.141.1,
  uvicorn[standard] 0.52.4, pytest 9.1.1, httpx 0.28.1, ruff 0.16.6, mypy 2.3.1, Pydantic 2.13.5.
- Storage: SQLite at `FLEXWEEK_DATABASE` (default `var/flexweek.db`), with users,
  sessions, weeks, preferences and short-lived auth-attempt counters. Schema
  creation is additive on startup; related writes use transactions. Browser
  localStorage is read only for explicit legacy import, then removed on success.
- Major components:
  - `backend/models.py` — Pydantic models (`TimeBlock`, `Move`, `SolveTrace`) and
    slot helpers. **Zero FastAPI imports.**
  - `backend/app.py` — HTTP endpoints, authentication/ownership, static files, `/api/solve`.
    No placement logic.
  - `backend/solver.py` — pure synchronous CSP placement. No HTTP knowledge.
  - `backend/explain.py` — reason code → English string. *(Not yet written.)*
  - `backend/storage.py` — SQLite transactions, password hashing and sessions.
  - `backend/data/demo_*.json` — test-only anonymized seed weeks.
  - `backend/tests/` — pytest suite; the source of truth for solver behavior.
  - `frontend/` — `index.html`, `styles.css`, `app.js`. The browser owns
    interaction and explanation display and **never reimplements placement**.
- Time model: local `HH:MM` strings and Mon–Sun day indices, assumed
  America/Los_Angeles. No timezone conversion math anywhere in v1.
- Slot grid: Mon–Sun 06:00–23:00, 15-minute slots, 68/day × 7 = 476/week.
  Overlap uses half-open ranges `[start, end)`. One `overlaps()` helper — no
  duplicate date math.
- External APIs/services: none. No OAuth, no calendar sync, no LLM at runtime.
- Deployment: hosted web backend plus separate desktop client (provisional
  Windows/Linux). Desktop shell/installer implementation belongs to Phase 5.
  Production requires HTTPS via FLEXWEEK_ORIGIN and persistent SQLite storage.

## Security & Privacy
- No secrets in source. All credentials via environment variables. The app
  uses account session credentials generated at runtime.
- Dependencies must be pinned and reproducible. Updates are manual:
  **Dependabot is deliberately not used in this repo** — do not add
  `.github/dependabot.yml` or re-enable it.
- Account-owned schedules are sent to the backend and stored in SQLite.
- Passwords use Python/OpenSSL scrypt, N=32768, r=8, p=3, random 16-byte salt,
  32-byte derived key; comparison is constant-time. No new hash dependency.
- Opaque random sessions expire in seven days; only SHA-256 token hashes are
  stored. Cookies are HttpOnly, SameSite=Strict, Secure on HTTPS deployments.
  Sign-out revokes the current session. Expired sessions are rejected on reads
  and cleaned when new sessions are created.
- Writes use custom-header/origin CSRF checks; endpoints derive ownership from
  the session. Queries are parameterized. No credentials or schedule payloads
  are logged; validation responses omit submitted input.
- Auth attempts are bounded per username (10) and source address (30) per
  five-minute window, persisted in SQLite and expired during auth requests.
- Production needs HTTPS, database backups, and deployment-specific proxy setup.
  Recovery, deletion/retention policy, advanced hardening and audits are deferred
  to Phase 6 before public release.
- Failed saves retain in-memory drafts with retry, download and reload controls.
  Stale revisions never silently overwrite newer data. Session loss hides all
  private content; a draft can restore only after the same account signs in.
  Explicit sign-out discards drafts after confirmation.
- Demo data is anonymized: no real student names, schools, or addresses, and no
  copyrighted syllabus PDFs in the repo.
- License is **GPL-3.0** (`LICENSE`); the README and the page footer must agree
  with it. Chosen deliberately: copyleft means anyone who redistributes a
  modified FlexWeek has to publish their source, so the scheduler cannot be
  quietly repackaged into a closed product that students cannot inspect.
- AI assistance is disclosed in the README and the CAC form; the solver is
  handwritten.

## Validation & Tooling
All three commands run from the repo root, inside `.venv`, and must exit 0:

- Lint: `ruff check .` — configured in `ruff.toml` (target `py314`, line length
  110). The `DTZ` (timezone-aware datetime) rules are deliberately not selected
  because of the naive-local-time model above; the reason is written into
  `ruff.toml`. Do not add timezone math to satisfy a linter.
- Types: `mypy backend` — mypy is this repo's type checker. `Github
  Templates/ci.yml` names `pyright` instead; that template is generic and this
  repo deliberately diverges, because mypy installs from `requirements.txt` with
  no Node toolchain.
- Tests: `pytest -q` — run from the repo root so `backend` imports resolve.
- Frontend behavior tests: `node --test frontend/tests/accounts.test.mjs`;
  syntax: `node --check frontend/app.js`. Node is development-only, with no npm
  packages or frontend build step. Browser layout needs a separate manual check.
- Preserve existing solver fixture coverage; include account isolation, expiry,
  CSRF, atomic saves, revision conflict and import/retry tests.
- Solver tests are the source of truth: `solve()` stays synchronous and pure so
  pytest can exercise it without HTTP.

## Acceptance Criteria
- [ ] Only-locked week solves to an identity schedule with 0 moves (T1).
- [ ] A single homework block with room to spare is placed, energy-matched where
      possible (T2).
- [ ] Test vs. reading contending for one slot: test placed, reading unplaced
      with `PRIORITY_PREEMPT` (T3).
- [ ] 6h of homework into 2h of free time: remainder unplaced with
      `NO_SLOT_LEFT` (T4).
- [ ] Deadline before the only free window: unplaced with `DEADLINE_MISS` (T5).
- [ ] A flexible block's domain excludes slots covered by a sport block (T6).
- [ ] The packed fixture reports `solve_ms < 150` (T7).
- [ ] Corrupt legacy localStorage does not replace the account week or load demos.
- [ ] Two accounts independently create, solve, save and reload weeks.
- [ ] Sign-out hides private data; expired sessions cannot read/write/solve.
- [ ] Nocturne/Slate theme persists per account.
- [ ] Failed saves preserve drafts; stale saves return a recoverable conflict.
- [ ] No output block overlaps another, and no flexible block starts after its
      deadline (property tests).
- [ ] A public Render URL loads the app and a judge can follow the README.
- [ ] `ruff check .`, `mypy backend`, and `pytest -q` all exit 0.
- [ ] CHANGELOG.md updated for user-visible changes.
