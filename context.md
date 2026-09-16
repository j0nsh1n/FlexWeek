# context.md — FlexWeek

## Current State
- Date: 2026-09-15. Audit of the Stage 6 backend, Stage 6 frontend and Stage 7
  month API on `grok/stage7-month-backend`: one own review plus three
  read-only GLM 5.3 Flash passes through `opencode` (security, month
  correctness, frontend security/accessibility). Fixed: password check moved
  inside the write transaction for recovery-codes, delete and export; month
  label rejects Unicode digits; completed sessions pin `completed_day` only.
  Tests added for wrong-password 401s, CSRF on every Stage 6 write, recover
  dropping other sessions, pomodoro chunks, completed-overdue and Unicode
  labels. Open for Claude: `aria-live` on `#recovery-status` and
  `#account-sync-note`, announcing or focusing the transfer preview, focusing
  the auth screen after account deletion. Open for the owner: stored open
  sessions never carry `start` (placements live only in the page), so month
  `session_count` and project `session_dates` reflect completed sessions and
  pomodoro chunks; `GET /api/day` counts a completed multi-candidate session
  on every candidate day (Stage 2 shape, unchanged). Nothing pushed.
- Date: 2026-09-15. Stage 7 month API is on `grok/stage7-month-backend` (worktree
  `~/.worktrees/flexweek-stage7-backend`), based on `grok/stage6-transfer-limit`
  at f268b7e. `GET /api/month` returns a clipped complete-week grid, deadlines,
  placed-session counts, projects and overdue homework against the proposed
  contract in `docs/stage7-contract.md`. Claude still owns Month view and
  date-to-Day navigation. Year view is out of this slice. spec.md drift:
  `GET /api/month` and the month grid rules are not in the public API table
  until the owner approves the contract. Full source gate
  (`scripts/verify.py`, desktop included): 221 frontend tests, 351 Python
  tests; a live uvicorn probe of the month route matched the contract. No
  executable was built. Nothing pushed.
- Date: 2026-09-15. Stage 6 contract approved and recorded in `spec.md` on
  `grok/stage6-transfer-limit`. Recovery, deletion, storage identity, previewed
  format-3 transfer and the 256 KiB import-apply envelope are product contract.
  Hosted Render deployment, installers and Safari/iPhone checks are skipped by
  the owner. Remaining Stage 6 work is the security/accessibility review.
  Stages 4 and 5 stay proposed and off the public API table. Web-only gate
  unchanged: 221 frontend tests, 263 Python tests. Nothing pushed.
- Date: 2026-09-15. Transfer size limits are reconciled on
  `grok/stage6-transfer-limit`, based on `feat/stage6-access-frontend` at
  bdfbb61. Export 413s when the import apply envelope would exceed 256 KiB.
  More than 400 small weeks can export when they still fit.
  `storage-info.transfer_limit_bytes` is 262144. Hosted deployment,
  security/accessibility review, installers and physical platform checks remain.
  spec.md drift: Stage 6 routes, storage-info fields including
  `transfer_limit_bytes`, and the transfer envelope rule await approval of
  `docs/stage6-contract.md`. Web-only gate: 221 frontend tests, 263 Python
  tests. Nothing pushed.
- Date: 2026-09-15. Stage 6 backend and shared frontend are complete locally on
  `feat/stage6-access-frontend`, based on Grok's backend at 6a5e3aa. Registration
  shows recovery codes once before setup; Forgot password, code replacement,
  password change and typed-username account deletion are wired. Settings name
  the username, local/hosted storage mode, origin and sync limit. Account
  transfer separates format-3 files from week files, names removals and requires
  review before replacement. The final source gate passes 218 frontend and 331
  Python tests, including real WebEngine and packaged-app smoke paths. A
  read-only Cartographer scan found 42 modules, 37 production routes and no
  parse errors, circular imports or scanner warnings. Hosted deployment, full
  security/accessibility review, installers and physical Safari/iPhone checks
  remain. The backend still needs one transfer-limit follow-up: a valid export
  can grow past the import request cap, and accounts above the 400-week export
  validation cap can fail to export. spec.md drift: the Stage 6 routes and
  storage fields await approval of `docs/stage6-contract.md`. No executable was
  built and nothing was pushed.
- Date: 2026-09-14. The Stage 5 shared frontend is complete locally on
  `feat/stage5-comfort-frontend`, based on Grok's backend at 10c9334. Settings
  now use Appearance, Focus, Notifications and Account sections; presets and
  split preview explain 15-minute rounding; local alert previews honor volume
  and never spend reminder keys; and the preferred view plus sidebar state
  survive reload. Live browser verification caught and fixed null sidebar width
  saves and collapsed-sidebar phone overflow. A Stage 5 WebEngine walkthrough
  covers the same path. The Qt shell still needs to apply start-at-login and a
  tray Test action. spec.md drift remains pending contract approval. No packaged
  executable was built and nothing was pushed.
- Date: 2026-09-14. Student-experience Stage 5 backend is on
  `grok/stage5-comfort-backend` (worktree
  `~/.worktrees/flexweek-stage5-backend`), based on `feat/stage4-adaptive-plans`
  at 6ae893c. Comfort preference fields, timer-split preview, timer presets and
  reminder-limit copy live behind the proposed contract in
  `docs/stage5-contract.md`. Claude still owns the Settings grouping, Test
  reminder, volume slider and remembered-layout UI. Desktop start-at-login and
  tray Test are stored as prefs, not applied by the Qt shell yet. spec.md
  drift: those fields and routes are not in the public API table until the
  owner approves the contract. Web-only gate: 195 frontend tests, 243 Python
  tests. Nothing pushed.
- Date: 2026-09-14. Student-experience Stage 4 is complete locally on
  `feat/stage4-adaptive-plans` (worktree
  `~/.worktrees/flexweek-stage4-adaptive-plans`). Running late previews 15/30/60
  minute delays and stores one locked interval on accept. Spread, assignment
  notes/links/checklist, protected time, preferred study hours and cutoff are
  in. Priority and energy labels changed; stored values did not. Cluster advice
  stays visible. spec.md drift: `running_late`, spread, assignment project
  fields, availability prefs and the stored late block are not in the public
  API table until the owner approves `docs/stage4-contract.md`. Full source gate
  green: 195 frontend tests and 303 Python tests, including the Stage 4
  WebEngine walkthrough. Packaged binaries were not run. Nothing pushed.
- Date: 2026-09-14. Student-experience Stage 4 backend is on
  `grok/stage4-adapt-backend` (worktree
  `~/.worktrees/flexweek-stage4-backend`), based on `claude/stage3-frontend` at
  9759a23. Running-late solve preview, project-spread preview, assignment
  notes/links/checklist, preference occupancy (protected windows, study hours,
  day cutoff) and a deadline-cluster explanation live behind the proposed
  contract in `docs/stage4-contract.md`. Claude still owns the shared frontend.
  Nothing pushed. Web-only gate on this tree: 163 frontend tests, 229 Python
  tests (`ruff check .`, `mypy backend`, `pytest` on `backend/tests`). Desktop
  and packaged binaries were not run.
- Date: 2026-09-14. Student-experience Stage 3 is complete locally on
  `claude/stage3-frontend`: Codex's frontend (copy, paste, duplicate and copy
  day with conflict previews, fixed-only routines, unfinished-homework review,
  restore points and the Settings storage label) on Grok's backend (routines,
  restore points, storage-info, operation ids and snapshot labels on
  `/api/changes`, cherry-picked unchanged as a6b484f). Claude finished the
  WebEngine step and reviewed the code with two GLM adversarial passes, fixing
  seven defects. GLM findings that did not hold up against the source are
  listed as rejected in the commit messages. Jonathan confirmed the contract
  on 2026-09-14, and spec.md lists the Stage 3 routes.
- Full source gate green on the final tree: 163 frontend tests and 278 Python
  tests, including the real Qt WebEngine `stage3` case (copy, routine apply,
  restore, a retried operation, reload, a second account) and `stage3_mobile`
  (390px dark theme, unfinished homework carried once). The T3 preview browser
  could not load a local server, so no separate live browser pass ran. No
  package or executable build ran. Nothing pushed.
- Date: 2026-09-14. Student-experience Stage 2 is complete locally on
  `feat/stage2-student-experience` (the same commits as
  `claude/stage2-frontend`): Grok's `GET /api/day` plus the Day agenda, Day
  first at 800px and narrower, quick Add homework, Plan my homework / Update my
  plan wording, collapsed results with slack in days, Export and Import in
  Settings, and Edit / Finished / Start focus in agenda rows. It follows the six
  proposed defaults in `docs/stage2-contract.md`, which is not approved yet, so
  spec.md does not list `/api/day`. Full source gate green: 145 frontend tests
  and 250 Python tests, including the stage2 WebEngine probe at 390px and
  1280px. No remote branch changed.
- Date: 2026-09-13. Student-experience Stage 1 is complete locally on
  `feat/stage1-student-experience`. The branch combines the seven-stage roadmap,
  approved contract, reviewed backend and finished frontend: exact assignment
  deadlines and cross-week sessions, Continuing and Plan the rest here, focus
  outcomes and reload-safe timers, Undo/Redo, safer deletes, and version 2
  export/import. No remote branch changed.
- Full source verification after integration is green: 139 frontend tests and
  241 Python tests, including the Stage 1 Qt WebEngine walkthrough. A live
  browser check also covered assignment entry, next-week Continuing, Solve,
  and the Finished / Need more time / Take a break prompt. A read-only
  Cartographer scan found 28 Python files, 16 routes, no parse errors, no
  circular imports and no scanner warnings.
- Date: 2026-09-11. v0.9.2 is released (PR #9, tag at a20831f).
  `feat/frost-reference-look` (5ca38b7, restyle after the owner's reference
  dashboards) is parked and in neither release.
- v0.9.1 shipped: a page renderer that stops reopens solved and solid instead of
  a blank window; `--smoke-test` walks setup to its Solve with a pixel check;
  the AppImage `.sha256` names only the file; AppImage FUSE doc tip.
- v0.9.2 replaced the Windows zip with per-account Setup.exe and per-machine
  MSI installers, built and exercised on the GitHub Windows runner.
- The owner sees flicker in the setup dialog on Windows and is investigating
  that directly. On the owner's Linux PC (KDE Wayland, RX 9070, Mesa 26.2.2) blur on,
  blur off and GPU off all looked the same, with no flicker.
- Hybrid frost visual system is in: one token map per theme in
  `frontend/styles.css` (`:root` = nocturne/dark, `[data-theme="slate"]` =
  light), frosted chrome with a solid fallback, near-opaque week grid, soft blue
  accent, Figtree font and a duotone SVG icon sprite in `index.html`.
- Gates green 2026-09-10 via `scripts/verify.py`: ruff, mypy over 22 files,
  184 Python tests (real WebEngine probes, now checking the Figtree face loads
  and signed-out pages start light) and 95 frontend tests.
- Windows execution on a real PC, Safari/iPhone, physical touch and OS
  notification delivery remain unverified. Hosted web URL is not online.
- Default desktop mode uses a local database. Hosted mode uses the configured
  server; there is no automatic synchronization between them.

## Repo Landmarks
```
docs/cac-build-plan.md   original Sep 6 contest brief (working title Reslot)
.github/workflows/       verify.yml (mypy), codeql.yml, release packages
DESKTOP.md               PySide6 QWebEngineView recommendation + build status
desktop/origin.py        origin resolution, no Qt imports (unit-tested)
desktop/server.py        bundled uvicorn on a loopback port, no Qt imports
desktop/main.py          Qt window, persistent profile, retry panel
desktop/build_linux.sh   staged Linux build, previous artifacts preserved
desktop/package_linux.sh release tar.gz with README, icon and .desktop
desktop/check_bundle.py  glibc and missing-library check, no Qt imports
desktop/build_windows.ps1 Windows standalone build preparation
desktop/tests/           origin/server tests and isolated real WebEngine probes
backend/weeks.py         week-date helpers, no framework import
backend/recovery.py      one-time recovery codes, no HTTP
backend/limits.py        256 KiB write-body cap
backend/transfer.py      import apply envelope size, no HTTP
backend/restore.py       restore-point snapshot diff and token, no HTTP
backend/app.py           account/session/ownership APIs and static frontend
backend/storage.py       SQLite, scrypt, hashed sessions
frontend/app.js          week state, grid, saves, solve, alarms, CATEGORIES table
frontend/editor.js       Add/Edit dialog: draft -> draftProblem -> draftPatch
frontend/setup.js        first-week setup, built on editor drafts
frontend/focus.js        focus timer, Now / Next line
frontend/reuse.js        clipboard, duplicate, copy-day and homework carry-forward
frontend/routines.js     fixed-only weekly routine templates and apply preview
frontend/restore.js      clear-week recovery and restore-point controls
frontend/auth.js         Create account / Log in screens, session start (loads last)
frontend/tests/app-scripts.mjs  loads index.html's scripts in order for DOM-stub tests
frontend/tests/stage3.test.mjs  Stage 3 retry, identity, conflict and rollback cases
frontend/styles.css      both theme token maps, then components that only read tokens
frontend/fonts/          Figtree variable font + OFL license, served from /static
frontend/theme.js        System/Light/Dark choice -> data-theme, loaded in <head>
frontend/tests/theme-tokens.test.mjs  token parity, no raw colors, no-blur contrast, accent vs categories
```

## Domain Model
SQLite: users → sessions, many dated weeks keyed (user_id, week_start), one
preference row. Default desktop
mode uses a local per-user database; hosted mode uses the configured deployment.
There is no automatic synchronization between those databases.
Assignments are keyed (user_id, id) with a JSON body and revision. A
flexible block with `assignment_id` is a work session of that assignment.
Routines are keyed (user_id, id) as named templates of locked blocks.
Restore points snapshot all of an account's weeks and assignments.
Recovery codes are hashed per user and shown only once at register or regenerate.
A format-3 export can copy weeks, assignments, preferences and routines onto
another account after a preview. There is no automatic local/hosted sync.
Recorded `operation_id` values make a retried write return the first result.

## Non-Obvious Decisions
- A week's identity is its Monday. Blocks store a day index and derive their
  date, which is why the day-index solver needed no adapter at all.
- `weeks.py` pins the ISO shape with a regex before parsing, because
  `date.fromisoformat` also accepts "20260907" and "2026-W37-1".
- The migration is guarded on the weeks table existing, since PRAGMA
  table_info returns nothing for a missing table and ALTER TABLE would raise on
  a fresh database. It runs in an explicit BEGIN IMMEDIATE, not in
  executescript, which issues an implicit COMMIT.
- Registration no longer seeds a weeks row; the NOT NULL key would reject it,
  and a missing row already means an empty week.
- GET /api/week 422s a non-Monday rather than snapping it, so a client and
  server cannot disagree about which week is open while both think they won.
- The identical-blocks short-circuit deliberately runs before the revision
  check, preserving what the pre-dated code and tests already did.
- The desktop app bundles the backend and runs it in-process (owner asked for
  this 2026-09-07). It supersedes DESKTOP.md section 1, which said not to; that
  section's reasoning was about a *second process*, which this is not.
- The loopback port is chosen by binding a socket before create_app is called,
  because the backend pins its CSRF origin check and TrustedHostMiddleware to
  one exact origin. uvicorn is handed the already-bound socket.
- uvicorn runs with loop="asyncio" and http="h11" so the build does not depend
  on uvloop/httptools surviving being frozen.
- An invalid FLEXWEEK_*_ORIGIN is an error, not a silent fall back to local:
  a typo must not quietly open a different, empty database.
- The Qt profile is parented to the QApplication, not the window: parenting it to
  the window makes Qt warn "Release of profile requested but WebEnginePage still
  not deleted" and can crash on close.
- `profile_root()` reads QStandardPaths AppDataLocation, which derives from the
  application name, so main() sets that before building the profile.
- Nuitka is called directly instead of via pyside6-deploy, which rewrites its own
  spec with absolute machine paths on every run.
- Qt translations are included; stripping them made WebEngine warn about a
  missing en-US.pak at every start.
- PySide6 6.10+ documents Python 3.14. pywebview classifiers stop at 3.13.
- Qt WebEngine cannot be statically linked; onedir Chromium libs are expected.
- No Qt WebChannel / pywebview js_api in v1 (cookies and CSRF stay on the page).
- License file is GPL-3.0. Qt for Python is LGPLv3/GPLv2/commercial.
- Frontend scripts are classic deferred scripts sharing one global scope, not
  modules, so there is still no build step. A script's top-level code can only
  reach scripts loaded before it. The tests run them in index.html order.
- The tray icon path is anchored on the `backend` package, because Nuitka puts
  `desktop/main.py` at the bundle root as `__main__`.
- A new flexible task in the week on screen may use today onward. The solver
  does not know today's date, so without this it placed new homework on days
  already over.
- The dialog offers Fixed or Flexible only for a new item; editing keeps the
  existing kind, because converting needs completed_day and start cleanup that
  no flow asks for yet.
- Windows installers: the Inno `AppId` and the MSI `UpgradeCode` are fixed
  forever, since upgrades find the installed copy by them. The .exe is per
  account (`PrivilegesRequired=lowest`) for students; the .msi is per machine
  for school IT. Inno Setup is not on windows-latest, so CI downloads 7.1.0 and
  checks its SHA-256. WiX is pinned to 6.0.2 because v7 blocks every command
  until someone accepts its EULA.
- Windows ICU (icuuc/icuin) is a system DLL since 1703. Copying it out of
  System32 would redistribute Microsoft's files; the bundle check requires the
  import to be satisfied by Windows 10 1809+ instead.
- `theme` is `system|slate|nocturne` (default `system`, owner decision
  2026-09-10). CSS only knows slate and nocturne on `<html data-theme>`;
  `frontend/theme.js` runs in `<head>` so first paint already matches the
  device, and re-resolves on device changes only while the choice is system.
  Signed-out screens always follow the device.
- SQLite cannot alter a CHECK, so `allow_system_theme()` rebuilds an older
  preferences table once in one transaction; stored slate/nocturne are kept.
- Offscreen Qt ignores `setColorScheme`; the `system_dark` probe forces a dark
  device with `--blink-settings=preferredColorScheme=0`. A real KDE dark
  session does reach `prefers-color-scheme: dark`.
- Frost alphas are chosen so text passes WCAG AA composited straight over the
  page gradient with no blur; that is the case Qt WebEngine hits when blur is
  not drawn. The theme-tokens test computes it, so do not lower an alpha without
  rerunning it.
- The accent must stay at least CIE76 distance 15 from every category color
  (School blue is the near miss), enforced by the same test.
- Icons are an inline `<symbol>` sprite, not a file: `<use>` inherits
  `--icon-secondary` into the symbol only when the sprite is in the page.
- Linux leads with a tar.gz so the executable bit survives and no extra runtime
  is required. The AppImage ships too, but needs FUSE (libfuse2); without it
  the docs say `--appimage-extract` then `squashfs-root/AppRun`, or the tarball.
  Unused Qt `.qm` files are dropped; the Chromium en-US locale pack stays.
- A dead page renderer leaves Qt's view one flat near-white color, and a lost
  GPU context leaves it the page background color; neither reaches the page or
  shows a dialog. A GPU-process crash kills the whole app instead (Qt runs GPU
  in-process). Hence `renderProcessTerminated` recovery in `desktop/main.py` and
  the smoke's window-grab color count (a blank page is 1 color, the bare page
  gradient under 100, a solved week 400 or more on an 8 px grid).
- The 0.9.0 blank window was not reproduced on: source offscreen, the published
  v0.9.0 Linux build on Xvfb/llvmpipe with GPU compositing, tray and
  notifications on, accessibility on, or eight clock times across the week.
  Trigger still unknown; likely GPU/driver specific (0.9.0 added the only
  backdrop-filter rules) or Windows.
- Smoke runs use a temporary data folder. WebEngine writes profile files until
  its page and profile are destroyed, so `MainWindow.discard()` runs before the
  folder is removed, or empty cache folders come back.

## Session Handoff
- 2026-09-15, `grok/stage7-month-backend`: Audit done (own review + three GLM
  passes). Backend findings fixed and tested; three minor accessibility
  findings handed to Claude (see Current State); two product questions for the
  owner on what a month "session" means when placements are not stored.
  Nothing pushed.
- 2026-09-15, `grok/stage7-month-backend`: Stage 7 backend slice. Proposed
  contract is `docs/stage7-contract.md`. `GET /api/month?month=YYYY-MM` is
  authenticated and CSRF-free. Claude owns the Month UI. spec.md drift: the
  month route. Full gate: 221 frontend tests, 351 Python tests. Nothing
  pushed.
- 2026-09-15, `grok/stage6-transfer-limit`: Owner approved the Stage 6 spec
  updates and skipped hosted deployment, installers and iOS checks.
  `docs/stage6-contract.md` is approved 2026-09-15. `spec.md` now lists recovery,
  password, deletion, storage-info fields, transfer routes and the 256 KiB
  apply-envelope rule. Stages 4 and 5 remain proposed. Remaining Stage 6 work is
  the security/accessibility review. Nothing pushed.
- 2026-09-15, `grok/stage6-transfer-limit`: Export and import now share the
  256 KiB write cap. Export 413s when the compact `{snapshot, state_token,
  operation_id}` envelope would not fit import apply. The 400-week transfer cap
  is gone; `storage-info` reports `transfer_limit_bytes`. The page measures that
  envelope rather than raw file size. Remaining Stage 6 work is hosted
  deployment, security/accessibility review, installers and physical platform
  checks. `docs/stage6-contract.md` remains proposed; spec.md drift includes the
  new field and envelope rule. Web-only gate: 221 frontend tests, 263 Python
  tests. Nothing pushed.
- 2026-09-15, `feat/stage6-access-frontend`: Shared Stage 6 UI complete over
  backend 6a5e3aa. `frontend/access.js` owns displayed recovery codes, storage
  identity and previewed transfer state; `auth.js` owns the recovery session
  transition. Wrong password errors keep valid sessions, and account changes
  clear codes and snapshots. A WebEngine case transfers a real saved week
  between accounts. The final gate passes 218 frontend and 331 Python tests;
  the 401 guard mutation fails by clearing the signed-in account as expected.
  Remaining Stage 6 work is deployment, broader review and physical platform
  evidence. `docs/stage6-contract.md` remains proposed; `spec.md` still omits
  its routes. No executable built; nothing pushed.
- 2026-09-14, `feat/stage5-comfort-frontend`: Shared Stage 5 UI complete over
  backend 10c9334. New `frontend/comfort.js` owns presets, split previews, alert
  previews and remembered layout. Settings writes wait for in-flight layout
  writes; account changes discard stale previews. The Qt shell still needs
  start-at-login application and tray Test. `spec.md` still omits the proposed
  comfort fields and three routes. No executable built; nothing pushed.
- 2026-09-14, `grok/stage5-comfort-backend`: Grok's Stage 5 backend slice.
  Contract is `docs/stage5-contract.md` (still proposed). Comfort fields omit
  defaults so Phase 7 GET still matches. Split preview snaps 25/5 to 30/15.
  Auto-split with a 25-minute work length is 422. Claude still owns the
  Settings UI. Desktop autostart/tray Test is not wired. spec.md drift: comfort
  fields, `/api/timer-split-preview`, `/api/timer-presets` and
  `/api/reminder-limits`. Web-only gate: 195 frontend tests, 243 Python tests.
  Cartographer skipped (not installed in the project venv). Nothing pushed.
- 2026-09-14, `feat/stage4-adaptive-plans`: Stage 4 finished in this tree.
  Accepting Running late writes a locked "Running late" block through
  `/api/changes` then re-solves; a failed re-solve keeps its error status.
  spec.md drift: Stage 4 routes and fields stay off the public API table until
  the contract is approved. Nothing pushed.
- 2026-09-14, `grok/stage4-adapt-backend`: Grok's Stage 4 backend slice.
  Contract is `docs/stage4-contract.md` (still proposed). Running late is a
  solve preview that occupies `[from_start, from_start + minutes)` on one day,
  reuses `RESHUFFLE_AFTER_MISS` with a distinct sentence, and never drops
  unplaced work. Spread is `POST /api/assignments/{id}/spread` and does not
  write. Assignment notes, links and checklist omit empties. Preferences keep
  protected / study / cutoff in `availability_json`; `POST /api/solve` loads
  them. spec.md drift: those fields, `running_late` and the spread route are
  not in the public API table until the owner approves the contract. Claude
  still owns UI. Web-only gate: 163 frontend tests, 229 Python tests.
  Cartographer skipped (not installed in the project venv). Nothing pushed.
- 2026-09-14, `claude/stage3-frontend`: Stage 3 finished by Claude. Codex's
  frontend (857f43d, 1f569aa) and WebEngine case (d666a92) sit on Grok's backend
  (a6b484f, the same patch as cfb8c48 on `grok/stage3-reuse-backend`). a438d3a
  fixes a batch paste over-planning homework, long routine names failing Apply,
  a 409 leaving a save stuck, restore jumping to this week, shortcuts firing
  behind open dialogs and invalid preview rows starting checked. b8d74b2 extends
  the WebEngine walkthrough and adds `stage3_mobile`. 25d0884 keeps a stale
  preview from saving after a 409. Grok's docs commit 4bada61 is folded into
  this branch's CHANGELOG and context. Gotchas: runJavaScript does not hand
  arrays back reliably, so probes pass JSON text; port 8765 belongs to another
  local service; the T3 preview browser could not load a local server. Nothing
  pushed.
- 2026-09-14, `docs/stage3-contract`: proposed Stage 3 contract based on
  `claude/stage2-frontend` at 3b1f1c9. Claude owns the shared browser/desktop
  frontend; Grok owns migrations, routes and backend tests. The contract keeps
  clipboard, fixed-only routines, assignment-preserving carry-forward and
  durable restore points separate. Nothing implemented, built or pushed.
- 2026-09-14, `claude/stage2-frontend` and `feat/stage2-student-experience`:
  Claude's Stage 2 frontend on Grok's `254e086`. The Day agenda and quick Add
  homework live in `frontend/day.js`. Day view session times come from the week
  in memory and its plan, because placements are not stored; `/api/day` supplies
  the workload and each due-soon homework's unplanned minutes. Update my plan
  stays once a week has been planned in this page session (`planned` on the
  week state). Gate lessons: the theme guard reads an id such as `#add-…` as a
  hex color, so style by class; the desktop smoke flow waits on the setup
  button's text. Grok has not reviewed these commits. Nothing pushed.
- 2026-09-13, `grok/stage2-day-backend`: Grok's Stage 2 slice, `GET /api/day`.
  Claude still owns Day/Week UI, Add homework and Plan my homework copy.
  spec.md drift: the day endpoint is not in the public API table until the
  contract is approved. Nothing pushed.
- 2026-09-13, `docs/stage2-contract`: proposed Stage 2 contract in
  `docs/stage2-contract.md`. Base is `feat/stage1-student-experience` at
  130ee99.
- 2026-09-13, `feat/stage1-student-experience`: locally integrates the staged
  student-experience roadmap with the approved Stage 1 contract, reviewed
  backend, five frontend feature commits and the Qt WebEngine probe. Stage 1 is
  marked complete; Stage 2 is next. The full source verifier is green (139
  frontend, 241 Python), and packaging was not run during integration.
- 2026-09-11, `docs/readme-screenshots`: README screenshots in `docs/images/`
  (week light, week dark, setup), taken offscreen at 1.5x from the real app with
  a demo week and a Wednesday 16:20 clock; a readme test keeps every shown image
  present and none unused. v0.9.2 released with the Windows installers.
- Open: the owner is diagnosing the Windows setup-dialog flicker with a separate
  prompt (GPU/ANGLE/Qt renderer switches, then DevTools CSS toggles).
- 2026-09-11, `feat/windows-installers`: Inno Setup and WiX scripts in
  `packaging/windows/`, workflow builds, installs, shortcut-checks, smokes and
  uninstalls both; pull requests touching packaging run it without uploading.
  Docs and `desktop/tests/test_windows_installers.py` updated. Release notes in
  `docs/release-notes-v0.9.2.md`.
- 2026-09-11, `fix/0.9.1`: renderer recovery (shell reload with
  `?recovered=1`, solid panels, re-Solve, native panel on a repeat), extended
  smoke with pixel check and throwaway data, WebEngine `recovery` probe,
  basename AppImage checksum plus workflow check, AppImage FUSE and Windows
  shortcut doc lines, release notes in `docs/release-notes-v0.9.1.md`.
- v0.9.1 released and marked latest after CI smoke passed on all three builds.
- 2026-09-10, `feat/hybrid-frost`: token maps, frosted chrome, grid tokens,
  Light/Dark labels, slate signed-out default, Figtree, duotone icons, theme
  token tests and CHANGELOG. Before/after screenshots were taken offscreen in
  /tmp/fw-frost (not committed). Nothing pushed.
- Theme defaults to System per the owner's spec change (same day): API,
  storage migration, theme.js, menus and probes updated.
- Next: owner review of both themes on a real screen.
- Open: hosted web URL, a hand check of close-to-tray and of the Windows zip
  on a real PC.
