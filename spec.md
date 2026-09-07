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
High-school students, on a public URL, with no accounts and no sign-in. Demo
data ships with the app so a first-time visitor (including a contest judge) can
press Solve without entering anything. Secondary audience: CAC judges, who will
open the GitHub repo.

## Required Behavior
Contract for the finished app (must-ship set, feature-frozen Oct 3, 2026):

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
  both the browser form and the API; corrupt `localStorage` resets to a demo
  instead of crashing; an unknown demo name returns 404.

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

Current API surface:

| Method | Path | Behavior |
|---|---|---|
| GET | `/api/demos` | Both seed demos as JSON |
| GET | `/api/demos/{name}` | `alex` or `jordan`; 404 otherwise |
| GET/POST | `/api/solve` | 501 until the solver lands |

Target shape of `POST /api/solve`: a week payload in, a `SolveTrace` out
(`placed`, `unplaced`, `moves`, `failed_constraints`, `solve_ms`, `complete`).

## Architecture
- Language/runtime: **Python 3.14** — PINNED. Verified against the local
  interpreter (3.14.7) and `Github Templates/ci.yml` (`python-version: "3.14"`).
  Never downgrade.
- Ship exactly four languages: Python, JavaScript, HTML5, CSS. TypeScript and
  SQL are permitted only if they do real work; nothing else is added.
- Frameworks, pinned in `requirements.txt`: FastAPI 0.141.1,
  uvicorn[standard] 0.52.4, pytest 9.1.1, httpx 0.28.1, ruff 0.16.6, mypy 2.3.1.
- Storage: none. Demo weeks are JSON files on disk; the user's own week lives in
  browser `localStorage`. No database.
- Major components:
  - `backend/models.py` — dataclasses (`TimeBlock`, `Move`, `SolveTrace`) and
    slot helpers. **Zero FastAPI imports.**
  - `backend/app.py` — thin JSON door: static files, demo endpoints, `/api/solve`.
    No placement logic.
  - `backend/solver.py` — pure synchronous CSP placement. No HTTP knowledge.
    *(Not yet written — see context.md.)*
  - `backend/explain.py` — reason code → English string. *(Not yet written.)*
  - `backend/data/demo_*.json` — anonymized seed weeks.
  - `backend/tests/` — pytest suite; the source of truth for solver behavior.
  - `frontend/` — `index.html`, `styles.css`, `app.js`. The browser owns
    interaction and explanation display and **never reimplements placement**.
- Time model: naive local strings `YYYY-MM-DDTHH:mm`, assumed
  America/Los_Angeles. No timezone conversion math anywhere in v1.
- Slot grid: Mon–Sun 06:00–23:00, 15-minute slots, 68/day × 7 = 476/week.
  Overlap uses half-open ranges `[start, end)`. One `overlaps()` helper — no
  duplicate date math.
- External APIs/services: none. No OAuth, no calendar sync, no LLM at runtime.
- Deployment: one public URL on Render. No native app, no installer, no
  Electron. PWA manifest is optional and Week 6 only.

## Security & Privacy
- No secrets in source. All credentials via environment variables. The app
  currently needs none.
- Dependencies must be pinned and reproducible. Updates are manual:
  **Dependabot is deliberately not used in this repo** — do not add
  `.github/dependabot.yml` or re-enable it.
- No accounts, no auth, no user data leaves the browser.
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
- After Phase 2, run the T1–T8 matrix (see roadmap.md) on every change.
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
- [ ] Corrupt `localStorage` resets to a demo instead of crashing (T8).
- [ ] No output block overlaps another, and no flexible block starts after its
      deadline (property tests).
- [ ] A public Render URL loads the app and a judge can follow the README.
- [ ] `ruff check .`, `mypy backend`, and `pytest -q` all exit 0.
- [ ] CHANGELOG.md updated for user-visible changes.
