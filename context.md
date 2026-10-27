# context.md — FlexWeek

## Current State
- 2026-10-26: Preparing 1.2.0 on `fix/visual-artifacts-20261026`. Jonathan selected Quiet split
  plus the Settings and Unfinished fixes, with the earlier renovation kept separate. Desktop and
  Android report 1.2.0; Android versionCode is 4. Release notes are `docs/release-notes-v1.2.0.md`.
  PR #54 is open with the reviewed source; no 1.2.0 tag or release exists yet.
- Quiet split removes the repeated status row, moves Week as a list into More, keeps Ctrl+Shift+L
  and focus return, quiets Plan, and separates the rail with type and spacing. Light, Dark at
  1024x640 Large, and High contrast each passed all 15 real-KWin pointer and shortcut steps.
  Logs and captures: `~/.flexweek-ui-harness/scratch/quiet-split-ui/integrated/`.
- Setup's mismatched test clock now holds Monday 09:00; no planner change. Retro's late-month
  fixture now has a visible deadline; ten slide tests pass and the repaint mutation is caught.
  Bento's background-refresh focus loss reproduced before preserving the window's remembered
  focus; 20 related tests and both real-KWin focus checks pass after the fix.
- The rebuilt fwtest runner's final gate passed: 5422 tests, Ruff, mypy, mutation anchors and
  whitespace checks (581.08s, service peak 4.1 GiB). The Plan mutation catches loss of accent text. Harness and engine
  fmt, clippy and tests pass. Cartographer's launcher cannot import the traceworks module.
- Android unit tests and the release build pass. The signed 1.2.0 APK retains 1.1.1's certificate.
  Release artifacts and verification logs are in integrated scratch. Independent Grok 4.6 review
  passed on `007ba1ff`, with 47 focused tests. Windows/Linux CI packages remain pending.
  Its overdue announcement finding remains unverified with a screen reader: the event targets
  the hidden Unfinished control. No release blocker was found.
- PR #54's Classic Week rig exposed a fixed-height Unfinished list forcing Large text above
  640 px. The list now keeps one whole row visible and scrolls when height is short. The exact
  1024x640 real-KWin scenario and 26 related tests pass. Restoring fixed height makes the new
  regression fail at 1024x776. Final gate and Classic Week rig are being rerun before the push.
- `feat/refined-look-renovation` remains separate at `4f1b9f97`, with its previously recorded
  772 focused tests and ten-look captures under `scratch/theme-renovation-2026-10-26/`.
  Its uncommitted spec/changelog drafts were preserved as patches under the integrated scratch
  folder before removing those changes from the 1.2.0 documents.
- Latest published release is 1.1.1. The source trial was launched earlier from this task branch;
  its log is `~/.flexweek-ui-harness/scratch/manual-trial-20261026/desktop.log`.
- Since 0.18.5: new accounts start on a 12-hour clock (the desktop conftest sets 24-hour per test
  unless a test chooses); tests fail on any error inside a Qt slot (`no_error_is_lost_inside_a_qt_slot`).
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
  count) and the Python gate through `fwtest gate`. The differential tests and the
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
- 2026-10-26, Quiet split / 1.2.0: Grok 4.6 built the chrome and rail; Codex reviewed the source,
  integrated the chrome, migrated accessibility/menu tests, corrected two test fixtures, and
  fixed background calendar focus loss. Jonathan authorized choosing recommended steps through
  release. Target: `j0nsh1n/FlexWeek`, PR into `main`, tag `v1.2.0`. The rebuilt runner's full gate
  passed 5422 tests plus lint, types, mutation anchors and whitespace. Rust fmt, clippy and tests
  pass; Android is built and signed. Grok 4.6 independently reviewed `007ba1ff`: PASS, 47 tests.
  PR #54 is open. Its fixed-height Unfinished failure is corrected: 26 related tests, sizing
  checks and all 19 real-KWin Classic Week scenarios pass; the new regression catches the old
  fixed height. Next: final gate and independent recheck of this correction, update PR #54,
  finish CI and packaging, verify all ten assets/checksums and packaged Linux MCP, then publish.
  No 1.2.0 tag or release exists yet. The earlier renovation remains separate.
- 2026-10-21, `main` fff4d064: **1.1.1 released** (PR #53, tag `v1.1.1`, Latest; all ten assets attached, every checksum verified). Linux packages carry `flexweek-mcp` (`--mcp` from the AppImage, the tar.gz launcher and the app); the release workflow smokes both, and the published AppImage and tar.gz were smoked again locally. spec.md's Releases section now names the Linux packages; Windows and Android do not carry the helper. Next: Bori moves to `<package> --mcp --read-only` (Bori agent, `.handoff/bori-calendar-mcp.md` section 12); release cleanup awaiting Jonathan's approval of the list; MCP track C (plan, running late, routines, restore) and the phone screens remain.
- Next (Jonathan's pick: MCP first): track C, Plan / Running late / explain tools, routines, restore, then the app switching to the Rust views, write door and restore so nothing is written twice. Duplicates until then: Python validators and homework-edit rules in `backend/` and `desktop/`, and the desktop's focus phase advance (`controller.py` `advance_focus`) beside the phone's in `engine/ffi/src/focus.rs`.
- Phone screens not built yet: full-screen focus with breaks (8 A), Month (6 B), Day (7 A), Week C with drag. Their plans are in `~/.flexweek-ui-harness/scratch/android-1.1/` (`rebuild-test-plan.md`, `wave4-test-plan.md`).
- Still waiting on Jonathan: what shrinks on My day and One thing at 1024x640 Large, and a device check of the phone updater and the lane 1 fixes.
- The Android release key lives in `~/.config/flexweek-android/` (outside the repo). Every phone update must be signed with it.
- Run plan: `~/.flexweek-ui-harness/scratch/1.1/plan.md`.
