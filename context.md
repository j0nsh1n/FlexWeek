# context.md — FlexWeek

## Current State
- 2026-10-20: The five requested desktop regression nodes pass individually through `fwtest` on
  `release/1.1`. Recovery now opens the session clock's day and week, restoring Agenda Start focus and
  My day's Running late. The overdue Plan question has exactly Plan into this week, Mark as finished,
  Not now. Both Clay now-pill nodes passed unchanged. Ruff across the repo, `mypy backend`, and the
  shared confirmation default/cancel test pass. No full gate or real-display check was run.
- 2026-10-16: 1.1 in progress on `release/1.1` (local only, nothing pushed). Merged: the phone release bugs
  (dark mode, Running late and Start focus hidden in release, Not now, reminder ids), the phone updating
  itself from GitHub Releases (rules from `engine/engine/src/desk/update.rs` through `engine/ffi`), and the
  desktop fixes (rail one-go message, sign-in pages scroll below 768 px, Replace timer and Restore sheets).
  Gate VERIFIED (5384 passed); 131 Android unit tests and 461 engine and ffi tests pass. The phone updater
  has not run on a device yet.
- 2026-10-14: fix-e implements per-design curated looks with shared palette tokens across app chrome, design canvases, Week, Day and My day. Missing per-design selections keep the account look, including High contrast; Setup persists a selected pack, and Settings names curated canvas looks. Existing accounts without a saved design look receive a one-time, device-local notice; new accounts completing setup on this computer are exempt. Review regressions, restored colour-safety coverage and the notice behavior are recorded in the fix-e lane report.
- 2026-10-13: 1.0.0 is prepared on `release/1.0.0` (worktree
  `~/.worktrees/flexweek-0190`, HEAD `a5f7384b`): the Android phone app
  (`android/`, Kotlin and Compose, package `com.flexweek.app`, minSdk 26) runs
  the real engine through UniFFI, and iroh device sync (`engine/sync`) pairs
  the desktop with an 8-digit code and syncs both ways through the n0 relay.
  A real Android phone paired and synced both ways on 2026-10-13 (mobile data
  through the relay; a same-Wi-Fi sync has not been separately reported).
  The v0.19.x features, look cards, polish and the wording sweep are in. The
  full gate is pending on the final head. v0.19.2 is the newest release.
- 2026-10-14 lane `fix-a` implemented the saved-session carry rule, phone clock-skew sync count, pairing sheet changes, and Android phone copy/layout. Rust workspace tests, Clippy, formatting, Python lane tests, and Ruff pass; Android unit tests need an Android SDK, which is not configured here.
- 2026-10-14 lane `fix-d2` makes Month and the Day dial strip follow the per-computer week-start setting while stored weeks and Week view remain Monday-based. `test_week_start.py` and `test_hours_month.py` pass through `fwtest`; Ruff passes on changed files. Before/after screenshots are in `~/.flexweek-ui-harness/scratch/1.0.0/shots-fix/fix-d2/`.
- Tests that pick a day of the current week on the real clock can fail on later weekdays since item
  2: hold the clock (`grid_support.hold_clock`, `session.now_ms`). The item-3
  and hours-open suites now hold their own clocks.
- Since 0.18.5: new accounts start on a 12-hour clock (the desktop conftest sets 24-hour per test
  unless a test chooses); tests fail on any error inside a Qt slot (`no_error_is_lost_inside_a_qt_slot`).
- Probing motion: `~/.flexweek-ui-harness/scratch/0.18.4/j14/claude-r3/probe_noprof.py` (copy into
  `desktop/tests/` as `test_zz_*.py`, run through fwtest with `-s`; `PROBE_DRAIN=1` waits for
  Settings' design previews, which otherwise land in the timed window; `PROBE_NOPROF=1` for real
  times). On-screen frames: `scratch/0.18.4/j15/clay_frames.py`.
- Rust (`engine/`, contract `docs/engine/contract.md`, wrappers `docs/engine/adapters.md`): the
  planner and solver, slots, weeks, day, month, explain, restore, recovery codes, the store's SQL
  helpers and database connection, and the desktop's Qt-free logic (`desk`: calendar, custom looks
  with saving, naming and import, files, focus, history, pomodoro, remind, reuse, tokens, update,
  week model). Python calls it through the `flexweek_engine` module; the Python wrappers only
  encode, call and decode.
- Python: the FastAPI routes (about 40 SQL statements remain in the route bodies of `create_app`),
  password hashing's random salt, the clock, the environment and file reads (the engine core is
  pure), the pydantic checks, `backend/models.py`'s Spotify and due-date copies, the `CATEGORIES`
  table in `calendar.py`, `TYPE_PT` in `tokens.py`, `custom_look.readability`, all Qt drawing, and
  `scripts/rig/drive.py`.
- Tests: the Rust engine suites (engine, store, bindings and sync; clippy and fmt clean at last
  count) and the Python gate through `fwtest gate --workers 4`. The differential tests and the
  frozen Python copies are deleted; the Python tests that remain guard Python-only code and the
  interface. Regression Tester's suites live in desktop/tests/regress184, regress190 and
  backend/tests/regress184, collected only with FLEXWEEK_REGRESS=1 (regress184 waits for its
  conftest); `scripts/rig/play.py` gives agents a play mode (steps, shots and widget trees).
  `hypothesis` is used by no test and still awaits Jonathan's word to go.
- Speed (`log.tsv`, pr35 review at 2e2f76a): placing the probe week 1.1 ms (0.17.2: 2.9 ms; with a
  busy second thread 1.0 ms against 8.0). Drawing a frame of the hours 10.2 ms median (0.17.2:
  9.1 ms; the limit is 16 ms).
- Known differences from the Python originals: integers past 64 bits and JSON only Python reads
  (NaN, lone surrogates) in stored rows; an assignment estimate past 2^63 raises `OverflowError` in
  the engine where Python returned a number (seen once under hypothesis); `build_month` returns a
  month where Python raised `TypeError` on a finished session with no start. About 100 cases the
  deleted differential tests pinned have no Rust test of the same case (list in the 0.18.1 scratch
  report).

## Repo Landmarks
```
engine/engine/          pure Rust core: plan, solve, day, month, restore, desk modules; tests/ are the Rust twins
engine/sync/            iroh device sync (`flexweek-sync`): apply, records, schema, peers, scan, and net/ (pair, protocol, session, service, qr)
engine/ffi/             UniFFI crate (`flexweek-ffi`) the Android app loads as libflexweek_ffi.so
engine/store/           Rust SQL helpers per table (assignments, ledger, prefs, routines, weeks, rules)
engine/py/              PyO3 binding built as `flexweek_engine` (`pip install ./engine/py`)
engine/clippy.toml      forbids key-reordering removes; `Cargo.toml` builds the engine at opt-level 2 in debug
docs/engine/            contract.md, adapters.md (every wrapper's class), interface-logic.md
tools/fwtest/           Rust test runner: gate, mutate, rig, run, clean; builds with cargo
scripts/mutations/      mutation specs (JSON); engine cases point at `cargo:` tests
scripts/rig/            Python rig driver for the hidden desktop (fwtest starts and stops the session)
backend/app.py          FastAPI routes: account, session, ownership; serves no pages
backend/storage.py      Python adapter over the engine's connection; scrypt and sessions
backend/{slots,weeks,limits,...}.py  wrappers that re-export or call the engine
desktop/main.py         launcher: starts the backend in-process, then the native window
desktop/server.py       bundled uvicorn on a loopback port, no Qt imports
desktop/native/window.py     chrome, pages, dialogs, autosave, updater wiring
desktop/native/controller.py session: saves, solve, focus, alarms, reminders
desktop/native/widgets.py    week grid, day agenda, month, editors, Add menu
desktop/native/layouts/      the eight designs; registry.py builds the dialog
desktop/native/look.py       packs, presets, palettes, the one stylesheet
desktop/native/version.py    VERSION, kept equal to the newest CHANGELOG heading
desktop/native/*.py          the Qt-free modules are thin wrappers over engine::desk
desktop/{build_*,package_*}  Linux and Windows builds; packaging/ holds AppImage, Inno, WiX
android/                the Android phone app: Kotlin + Compose, loads the ffi lib; scripts/android/ builds and signs it
desktop/tests/          widget tests, engine desk parity tests, `--smoke-test`
.github/workflows/      verify, codeql, release packages
```

## Domain Model
SQLite: users → sessions, many dated weeks keyed (user_id, week_start), one preference row. Default
desktop mode uses a local per-user database; hosted mode uses the configured deployment. There is no
automatic synchronization between them. Only the engine opens the database; the format is unchanged
from 0.17.2, so earlier passwords, sessions and recovery codes still work.
Assignments are keyed (user_id, id) with a JSON body and revision. A flexible block with
`assignment_id` is a work session of that assignment. Routines are keyed (user_id, id) as named
templates of locked blocks. Restore points snapshot all of an account's weeks and assignments.
Recovery codes are hashed per user and shown only once. A format-3 export can copy weeks,
assignments, preferences and routines onto another account after a preview. Recorded `operation_id`
values make a retried write return the first result.

## Non-Obvious Decisions
- The engine core is pure: Python reads the clock, environment, files and randomness and passes
  them in. JSON text crosses the boundary (a 12-block week costs about 0.02 ms to encode and decode).
- `serde_json` has `preserve_order` on, and `engine/clippy.toml` forbids the removes that reorder
  keys, so stored JSON keeps Python's key order.
- Colour maths calls the C library's `cbrt`, `pow`, `atan2`, `sin` and `cos`, looked up at run time
  (`desk/cmath.rs`: `libm.so.6`, `ucrtbase.dll` on Windows), so results match Python's to the bit.
- Case folding uses a table generated from this interpreter (`engine/tools/generate_casefold.py`),
  not a crate.
- The engine crate builds at opt-level 2 in debug so the solver's 150 ms budget holds under load
  (Jonathan's choice).
- A week's identity is its Monday. Blocks store a day index and derive their date. `weeks` pins the
  ISO shape before parsing, because `date.fromisoformat` also accepts "20260907" and "2026-W37-1".
- GET /api/week 422s a non-Monday rather than snapping it, so client and server cannot disagree about
  which week is open.
- The identical-blocks short-circuit runs before the revision check, as the pre-dated code did.
- The migration is guarded on the weeks table existing and runs in an explicit BEGIN IMMEDIATE.
  Registration seeds no weeks row; a missing row already means an empty week.
- A new flexible task in the week on screen may use today onward, since the solver does not know
  today's date. The dialog offers Fixed or Flexible only for a new item; editing keeps the kind.
- The desktop app bundles the backend and runs it in-process (owner's choice 2026-09-07). The
  loopback port is chosen by binding a socket before `create_app`, because the backend pins its CSRF
  origin check and TrustedHostMiddleware to one origin; uvicorn gets the bound socket and runs with
  `loop="asyncio"`, `http="h11"`.
- An invalid FLEXWEEK_*_ORIGIN is an error, not a fall back to local, so a typo cannot quietly open
  a different, empty database.
- `profile_root()` reads QStandardPaths AppDataLocation, so `main()` sets the application name first.
- Nuitka is called directly, since `pyside6-deploy` rewrites its spec with machine paths.
- `theme` is `system|slate|nocturne` (default `system`, owner decision 2026-09-10).
  `allow_system_theme()` rebuilds an older preferences table once, keeping stored slate/nocturne.
- The accent stays at least CIE76 distance 15 from every category colour; a test in
  `desktop/tests/test_look.py` holds it.
- Windows installers: the Inno `AppId` and the MSI `UpgradeCode` are fixed forever so upgrades find
  the installed copy. The .exe is per account, the .msi per machine. Inno Setup 7.1.0 is downloaded in
  CI with its SHA-256 checked; WiX is pinned to 6.0.2 because v7 blocks on an EULA. Windows ICU is
  required from Windows 10 1809 rather than copied out of System32.
- Linux leads with a tar.gz so the executable bit survives. The AppImage needs FUSE; without it use
  `--appimage-extract` then `squashfs-root/AppRun`, or the tarball.
- The smoke test decides a week was drawn by counting colours in a grab of the window
  (`PAINTED_MIN_COLORS`, 8 px grid): a blank window is one flat colour.
- The release workflow stops a Windows installer or smoke test that hangs after ten minutes.

## Session Handoff
- 2026-10-20, `release/1.1` (worktree `~/.worktrees/flexweek-0190`). Desk hand-move, the local schedule reader, and the phone lane are merged. This commit cuts 1.1.0. A pull request into `main` follows. The device check is skipped.
- 2026-10-20 desktop test slice: `0759806c` fixes recovery's opening day/week. The overdue Plan sheet's button order and redundant close button are fixed in this handoff's commit. All five named nodes pass individually; assertions and fixtures are unchanged. The full pre-release checks remain pending. Nothing pushed.
- Still open: Settings scroll (lane 4, parked until a real compositor check), a Mac session file refused because the owner check reads /proc/self, and a schedule reader that starts signed out stays on "Please sign in".
- Month and Day phone screens are not in this merge. `~/.worktrees/flexweek-11-probe` is a detached checkout at 5a72b3f6. Lane branches and worktrees are still in place.
- Still waiting on Jonathan: what shrinks on My day and One thing at 1024x640 Large, and a device check of the phone updater and the lane 1 fixes.
- The Android release key lives in `~/.config/flexweek-android/` (outside the repo). Every phone update must be signed with it.
- Run plan: `~/.flexweek-ui-harness/scratch/1.1/plan.md`.
