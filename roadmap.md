# roadmap.md — FlexWeek

Congressional App Challenge 2026. Submit **Sunday, Oct 25, 2026, 8:00 p.m. PDT**
(hard deadline Monday, Oct 26, 9:00 a.m. PDT). Phases map to build weeks; a
phase may span several implementation slices.

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
- Status: [x] Complete per owner 2026-09-06 (40 tests, create/solve/refresh and
  corrupt-storage reset verified in the browser). Open: partner bug list.

## Revised scope — 2026-09-06

Phase 3 is complete per the project owner. Earlier partner tasks remain recorded
above as outstanding non-code work. The next work expands FlexWeek into an
account-based app and web app, with Daily Scheduler's calendar interactions and
Nocturne dark appearance. Visual redesign and auditing are deferred.

Daily Scheduler reference: `../Local-Schedule-Assistant`, specifically
`views.py`, `dialogs.py`, `mainwindow.py`, `core.py`, and `theme.py`.
Its Qt widgets need browser equivalents; the existing FlexWeek solver remains
the scheduling engine. `../LitSieve` currently contains no application source,
so an authentication comparison is unavailable.

The phases below replace the old Phase 4–7 scope. Dates are planning targets;
the larger scope makes the previous Oct 3 feature-freeze target obsolete.
The owner selected a separate desktop application plus web app. Windows/Linux
are provisional desktop targets, matching Daily Scheduler. A shared web UI in a
desktop shell is proposed; shell selection follows compatibility testing.

## Phase 4 — Accounts and shared persistence
- Registration, sign-in, sign-out, and session restoration.
- New accounts start with an empty week; account screens replace the demo picker.
- Server-side, account-owned schedules replace anonymous browser persistence.
- Explicit import of an existing browser week into the signed-in account;
  successful import is repeatable without duplicating blocks.
- Basic protection: password hashing, expiring/revocable sessions, protected
  schedule and solve endpoints, ownership checks, CSRF protection, login
  throttling, bounded input, and secure production cookies.
- Daily Scheduler's Nocturne palette and Slate alternative, with a saved theme
  preference; functional layout first, visual redesign later.
- Completion target: two accounts can independently create, solve, save, and
  reload their weeks; sign-out removes the previous user's schedule from view.
- Status: [x] Complete 2026-09-07. Account/editor/solve/reload/theme/sign-out
  and two-account isolation verified in the real Qt WebEngine at 1280px and
  390px, alongside API and frontend state tests.

## Phase 5 — Daily Scheduler interaction port and app delivery
- Separate desktop packaging plus browser delivery, sharing the web UI and
  account backend where practical; Windows/Linux are provisional targets.
- Day/week/month/year navigation, previous/next and Today controls.
- Drag empty space to create, drag to move, edge resize, click to edit,
  context-menu actions, and equivalent form/keyboard/touch controls.
- Colored activity categories, copy/paste, duplicate/copy day, undo/redo.
- Recurring activities with explicit single-occurrence versus series edits.
- Export/import and completion state, followed by reminders where supported.
- Calendar dates and week selection added before cross-week editing; the
  existing day-index solver receives an adapter for the selected week.
- Completion target: the same account's saved changes appear in both clients;
  edits preserve valid times and show save errors without discarding work.
- Build order for the remaining interaction port (2026-09-08): A calendar
  drag/resize/create/context menus (15-minute snap) → D recurring occurrence
  vs series edit → F reminders → B categories → E export/import and
  completion. Clipboard, duplicate-day, and undo/redo stay deferred. Do not
  port Daily Scheduler AI chat, Google Calendar OAuth, or Qt custom painting.
- Status: [~] Linux desktop shell built and running 2026-09-07
  (`dist/FlexWeek/FlexWeek`), with popup/download fixes and preserved rebuilds.
  Dated weeks landed 2026-09-08: weeks keyed by calendar Monday, navigation,
  per-week client state, and a migration verified against the real desktop
  database. Slice A calendar interactions landed 2026-09-08 on
  `feat/phase5-calendar-interactions` (15-minute snap drag create/move/resize,
  select, double-click edit, context Edit/Delete, thin category colors).
  Slices D/F/B/E landed 2026-09-08: occurrence vs series edits, start reminders
  (web Notification + in-app toast; tray deferred), full category chips,
  export/import and completion. Still open: Windows execution, copy-paste,
  duplicate day, undo/redo.

## Phase 6 — Scheduling explanations, later design and hardening
- Priority and energy controls, explanation panel, click reason to highlight.
  The model already has priority/energy fields; remaining behavior is checked
  against the actual solver when this slice begins.
- Missed-block rescheduling, change list, and slack indicators.
- Dedicated UI design revision after the interaction port.
- Later security hardening, recovery flows, accessibility review and audits.
- Deployment preparation: persistent database storage, backup/restore and
  client compatibility checks, account-based onboarding instructions.
- Completion target: a signed-in user creates a week, solves it, understands
  unplaced work, and recovers from a missed block in both clients.
- Status: [~] Scheduling explanations, slack indicators and per-occurrence
  missed-block recovery completed 2026-09-08. Design, hardening, recovery-flow
  expansion, audits and deployment preparation remain.

## Phase 7 — Pomodoro timers, alarms, Spotify and Daily Scheduler features
- Pomodoro focus timer attached to placed blocks: configurable work/break
  lengths, long-break cadence, pause/skip/reset, and alerts on phase changes;
  timer state stays client-side per session.
- Split long blocks into pomodoro work chunks with break blocks on the grid,
  as a manual action and optional solver pass (Daily Scheduler's split-block
  behavior without the AI chat).
- Focus session counts per task in the sidebar, rolling into the existing
  completion state.
- Spotify links on tasks and blocks that open in Spotify, with optional
  embedded playback where the platform allows it; playback control needs a
  Spotify Premium account and is best-effort per platform.
- Built-in alarms independent of schedule blocks: named alarm times with a
  popup that must be dismissed or snoozed. Web alarms fire only while the
  app is open; the desktop shell can alert in the background where the
  platform allows.
- Alarm sound selector: Daily Scheduler's built-in tones (chime, soft,
  bright, low, glass) or a linked Spotify track/playlist as the alarm sound;
  if Spotify is unreachable at fire time, fall back to the built-in tone.
- Live "Now / Next" status line and a current-time line in the day grid.
- Block-start notifications with lead time, sound toggle and Do Not Disturb
  override; system tray with quick-open on supported platforms, building on
  the Phase 5 reminders work.
- Free-gap visualization highlighting openings for unplaced work.
- Settings dialog consolidating theme, notifications, alarms, timer defaults,
  Spotify links and account actions.
- Completion target: a student starts a pomodoro from a placed block, sets an
  alarm that plays a linked Spotify playlist (tone fallback when Spotify is
  unreachable), and split chunks survive save/reload in both clients.
- Status: [ ]

## Later (post-contest or only if Phase 5–7 are green)
- Stronger deadline-cluster insight on top of existing slack ok/tight/danger
  badges (no mental-health or IEP product claims).
- Simple assignment list or ICS file import — not live Canvas / Blackboard /
  Google Classroom OAuth, and not syllabus-photo ML for the contest demo.
- Rejected for CAC scope: syllabus OCR, LLM auto-reschedule chat, LMS API
  bridges, offline-first AI mobile shell.

## Phase 8 — Contest delivery (target Oct 18–25)
- Release bug fixes, app distribution and hosted web URL.
- README with account setup, both contributors and AI-assistance disclosure.
- Contest recording using an account-created schedule, plus submission form.
  This recording is separate from the removed product demo mode.
- Completion target: submission on Oct 25 evening, 2026.
- Status: [ ]

## First implementation slice — approved 2026-09-06

### Goal and user stories
1. As a student, I want an account so my schedule belongs to me across clients.
2. As a student, I want an empty starting week and reliable saves so I can plan
   my own work without sample schedules replacing it.
3. As a student, I want Daily Scheduler's dark theme so the planner feels familiar.

### Acceptance criteria
1. Given a new visitor, when they open FlexWeek, then they see sign-in and
   registration; protected APIs return 401 without a valid session.
2. Given valid registration details, when registration succeeds, then the
   student enters an empty week with clear add-block and add-task actions.
3. Given an existing account or invalid/oversized input, when registration is
   submitted, then a safe error is shown and no partial account is created.
4. Given a signed-in account, when a valid week is saved and the page reloads,
   then the same week is returned from that account's server-side storage.
5. Given two accounts, when either reads, saves, imports, or solves a week,
   then the other account's stored data cannot be accessed or overwritten.
6. Given expired or revoked credentials, when a request is made, then it fails
   with 401 and the client returns to sign-in without exposing cached data.
7. Given a save in another tab, when a stale save arrives, then it returns 409
   and offers reload/retry rather than silently overwriting newer work.
8. Given an old browser week, when its owner chooses import, then it is validated
   and saved once; retries do not duplicate blocks. Corrupt input shows a
   recovery message and never loads a demo or overwrites a saved account week.
9. Given the theme setting, when Nocturne or Slate is selected and reloaded,
   then the selected theme persists for that account.
10. Given an empty week or invalid duration, when Solve is pressed, then empty
    input returns an empty trace and non-15-minute durations return validation
    errors; existing overlap, sleep, deadline, and timeout behavior is retained.
11. Given a timeout or failed save, when the response fails, then the client
    preserves unsaved edits and clearly distinguishes them from saved work.

### Data and interface impact
- SQLite tables: users (unique normalized username, password hash),
  sessions (hashed opaque token, user, expiry), weeks (user, blocks JSON,
  revision), and preferences (user, theme). Foreign keys and unique ownership
  constraints link data; writes are transactional. No database exists today.
- Initial scope is one current week per account using the existing `TimeBlock`
  payload. Dated multi-week storage is a separate Phase 5 migration.
- Endpoints: POST `/api/auth/register`, `/api/auth/login`,
  `/api/auth/logout`; GET `/api/auth/me`; GET/PUT `/api/week`;
  GET/PUT `/api/preferences`. Saves carry an expected revision.
- POST `/api/solve` keeps its current payload/trace shape but requires a session.
  Demo endpoints and demo-loading UI leave the product; seed JSON can remain
  solely as test fixtures.
- Passwords use a maintained password-hashing implementation; sessions use
  HttpOnly, SameSite cookies with Secure in production and server revocation.
  CSRF/origin checks protect writes; SQL queries are parameterized. No password,
  token, or schedule contents enter logs. Python/OpenSSL scrypt provides password
  hashing without a new dependency; existing direct dependencies are pinned.
- Screens: register/login, account identity/logout, empty planner, theme control,
  import prompt, loading/saving/saved/error states. No background jobs initially;
  expired sessions are rejected at request time and cleaned periodically.
- Production storage includes the account database and backups; account deletion
  and retention policy are part of the later hardening scope before public release.

### Edge cases
- Empty and oversized usernames/passwords/week payloads; duplicate usernames;
  double-submit registration and import; atomic rollback on database failure.
- Expired session during edits, logout in another tab, cross-account browser
  reuse, stale revisions, offline/retry and server restart persistence.
- Existing anonymous data stays local until explicit import; invalid data is
  recoverable without sample-data fallback. Private API responses are not cached
  by a future service worker.
- Existing local day-index/time model stays intact for this slice. Calendar-date,
  midnight, recurrence, and daylight-saving boundaries belong to Phase 5's
  date-model work, before month/year navigation or cross-week drag is shipped.

### Deferred scope and open decisions
- First slice excludes desktop packaging, drag editing, recurrence, reminders,
  advanced security, audits, visual redesign, performance rewrites and unrelated
  refactors. These first-slice exclusions do not remove later roadmap work.
- AI chat/Ollama and Google Calendar OAuth are not part of the proposed port;
  native mobile store builds, payments and shared team schedules remain outside
  the proposed scope.
- Confirmed: separate desktop app plus web app (owner, 2026-09-06); provisional
  Windows/Linux targets match Daily Scheduler.
- Approved: username/password accounts and SQLite on the existing Python/FastAPI
  backend, with no demo mode; spec.md updated to match.
- Desktop shell recommendation (2026-09-07): PySide6 QWebEngineView loading the
  hosted origin; see DESKTOP.md. Installer implementation remains Phase 5.

## Spec reconciliation — 2026-09-07
- Accounts, storage, installed-app delivery, demo-free onboarding and expanded
  interactions replace the old explicit exclusions.
- spec.md now describes Pydantic models, HH:MM/day indices, the working solver
  and authenticated API. Demo endpoints have been removed.
- requirements.txt now pins the installed direct dependency versions listed
  in spec.md, including Pydantic, Ruff and mypy.
