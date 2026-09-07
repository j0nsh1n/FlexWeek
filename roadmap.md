# roadmap.md — FlexWeek

Congressional App Challenge 2026. Submit **Sunday, Oct 25, 2026, 8:00 p.m. PDT**
(hard deadline Monday, Oct 26, 9:00 a.m. PDT). Phases map to build weeks; a
phase may span several small PRs. "Complete when" conditions are verified
locally (tests pass, feature works).

## Phase 1 — Skeleton (Sep 6–12, 2026)
- Tasks:
  - Repo, GPL-3.0 license, README, ARCHITECTURE
  - `models.py`: `TimeBlock`, `Move`, `SolveTrace`, slot helpers — no solver
  - Seed `demo_alex.json` and `demo_jordan.json` from partner data
  - `index.html` + `styles.css`: 7-column grid 06:00–23:00, locked blocks
    painted, flexible tasks in the sidebar
  - `app.py` serves `frontend/` and `GET /api/demos`
  - Governance files: spec.md, roadmap.md, context.md, CHANGELOG.md
  - Partner: interview 3 students; two anonymized weeks, 8 tasks each
  - Register for CAC; confirm congressional district and that the Member hosts
- Complete when: `uvicorn` shows two demo weeks and `pytest` has ≥10 helper
  tests green.
- Status: [~] Code exit green 2026-09-06 (15 tests, both demos 8 flexible,
  logo in the topbar). Open: partner interviews/pitch, CAC registration,
  district confirmation.

## Phase 2 — Solver v1 (Sep 13–19, 2026)
- Tasks:
  - `solve(blocks) -> SolveTrace`: backtracking + MRV + forward checking
  - Locked intervals and deadlines; sleep 23:00–06:00 as a locked guard
  - Fixtures: empty, packed, impossible, one 3-hour paper due tomorrow
  - Debug panel in JS: `solve_ms`, placed count, unplaced titles
  - Partner: three break-it cases on paper, then in the app
- Complete when: 20 fixture tests green; the packed fixture solves or fails with
  `NO_SLOT_LEFT` under 150 ms and never hangs.
- Status: [~] Code exit green 2026-09-06 (37 tests, packed and both demos
  under 150 ms). Open: partner break-it cases.

## Phase 3 — Usable app (Sep 20–26, 2026)
- Tasks:
  - HTML forms: add / edit / delete, locked vs. flexible
  - Persist the last week in `localStorage`; demos stay as Python JSON files
  - Solve button → `POST /api/solve` → paint the trace
  - Validate `duration_min % 15 == 0` in the form and in the API
  - Corrupt `localStorage` resets to a demo instead of crashing
  - Partner: build a week from scratch; 10-row bug list; 8 realistic assignments
- Complete when: a new user can create, solve, refresh, and still see the week
  without the author's help.
- Status: [ ]

## Phase 4 — Must-ship complete (Sep 27–Oct 3, 2026)
- Tasks:
  - Priority and energy on the model and in search order
  - Explain panel: moves + failed constraints, using partner copy per reason code
  - Click a move → highlight that block
  - Test: last good slot, test vs. reading → reading unplaced, `PRIORITY_PREEMPT`
  - Partner: 5 classmates test for 10 minutes unsupervised; keep 3 quotes
- Complete when: the storyboard runs end to end — load demo → solve → click
  unplaced → read the why. **Feature freeze Oct 3.**
- Status: [ ]

## Phase 5 — Cascade + slack, or polish (Oct 4–10, 2026)
- Go / no-go Monday Oct 4: if Phase 4 is red, polish only and skip these.
- Tasks:
  - "I missed this block" → re-solve → list diffs
  - Deadline slack hours with ok / tight / danger badges; sleep never stolen
  - Partner: time the 90-second demo around the miss-and-ripple beat
- Complete when: the video beat works — miss → ripple → reasons.
- Status: [ ]

## Phase 6 — Contest surface (Oct 11–17, 2026)
- **Hard feature freeze Sunday Oct 11, 6:00 p.m.**
- Tasks:
  - Keyboard access, contrast, reduced-motion, empty states
  - Deploy to Render; README a judge can follow; both names on the README;
    disclose AI assistance
  - Test Safari on an iPhone once
  - Partner: final script and B-roll
- Complete when: a public URL loads the app and the README walks a judge through it.
- Status: [ ]

## Phase 7 — Ship (Oct 18–25, 2026)
- Tasks:
  - Bugfixes only
  - 90-second demo video, filmed and edited
  - CAC submission form
- Complete when: submitted the evening of Oct 25, 2026.
- Status: [ ]

## Kill list if a week slips
| Behind after | Cut |
|---|---|
| Phase 2 | Energy (keep priority only) |
| Phase 3 | Drag-and-drop, forever |
| Phase 4 | Phase 5 cascade + slack |
| Phase 5 | Grade-impact overlay, TypeScript rewrite, SQL |
| Phase 6 | All code except crash fixes |

## Test matrix (run T1–T8 on every change after Phase 2)
| ID | Case | Expect |
|---|---|---|
| T1 | Only locked school | Identity schedule, 0 moves |
| T2 | One homework, plenty of room | Placed, energy-matched if possible |
| T3 | Test vs. reading, one slot | Test placed, reading unplaced, `PRIORITY_PREEMPT` |
| T4 | 6h homework, 2h free | Unplaced remainder, `NO_SLOT_LEFT` |
| T5 | Deadline before school ends | Unplaced, `DEADLINE_MISS` |
| T6 | Sport overlaps homework | Homework domain excludes sport |
| T7 | Packed fixture | `solve_ms < 150` |
| T8 | Corrupt storage | Reset to demo |
| T9 | Miss locked sport (Phase 5) | Downstream flexible moves; sleep intact |
| T10 | Slack danger (Phase 5) | 0 float → danger |

## Backlog (unscheduled)
- Grade-impact overlay as a priority input (stretch; only if Phase 5 finishes by
  Oct 10)
- PWA `manifest.json` (Phase 6 only, optional)
- SQLite instead of JSON files (optional, only if JSON becomes painful)
- TypeScript for the UI (optional, only if JS gets messy after Phase 3)
- ICS import (post-contest idea; not OAuth)
- Better duration estimates from past completions
- CI: install `Github Templates/ci.yml` and `codeql.yml` into `.github/workflows/`
  (needs a ruff config decision first — see context.md)

## Out of scope (cut before Phase 1)
LLM chat, Google Calendar OAuth, accounts, native iOS/Android, Electron or .exe,
time-estimation learning, shared/team CRDT, payments, live AI as the product,
Java/Swift/C++/Kotlin/PHP/Ruby, Dependabot.
