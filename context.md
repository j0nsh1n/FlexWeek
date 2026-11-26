# context.md — FlexWeek

## Current State (2026-11-26)
- 2026-11-26: all of P4 group 5 is merged (#194 5C Unfinished counts, #195 5B Running late and previews, #196 5A
  Plan), with groups 2-4 before it (#181, #184-#186, #188-#190). Also merged today: #191 (School deleted "this week"
  or "this day" goes into `removed_days`, not `missed_days`), #192 (Sign out row in Settings > This computer;
  signing out from Settings resets Settings to the week), #193 (an update saves the week before it installs) and #197
  (CI installs the pinned Rust 1.98.1 with rustfmt and clippy before cargo runs). `controller.py` is about 4,000 lines.
- Material 3 desktop redesign ("2.0 richer", branch `feat/design-2-richer`, PR #182) updates all main Material
  screens: 5-step tonal surfaces in `theme.py` (`B3A3`), `M3Palette` semantic surfaces/corners/scrim/shadow tokens,
  Week Option A (elevated calendar card, tonal homework drawer, category icons), Day Option B (full-height timeline
  with draggable/keyboard-resizable right Now + mini-month sidebar remembered as `material.daySideWidth`), My day
  Option B (horizontal hero banner with ring + side-by-side Up next and Done cards), Settings Option A (icons,
  group headers on all cards, resizable section list remembered as `material.settingsNavWidth`, separate `Phone &
  sync` section, centered A+C `PairingDialog`), Sign in Option B (animated 5-scene QML showcase pausing on hover
  and static under Reduce motion/Off), Setup (top stepper, 2x2 choice grids, pinned footer), and Update (centered
  B+C hybrid pop-up). Proposed `spec.md` updates are staged for approval outside git.
- `origin/main` is `9f5d5b1d`. Latest release: v1.5.0, published 2026-11-20 from `0effa56f` (PR #141). The 2.0.0 Rust
  overhaul is under way on main and is available in developer builds only.
- P0 (#142), P1 (#143-#152) and the P2 server removal (#154-#156) are merged. The window asks the Rust service in its
  own process. `desktop/server.py`, `desktop/origin.py`, `backend/app.py` and FastAPI/uvicorn/httpx are gone, and the
  hosted-server settings are not read. With no phone paired, the app opens no network port. Removing pydantic is part
  of P4.
- P3 is done (#158, #160): the test-only door (`desktop/tests/door.py`, `door_app.py`) and `flexweek-testkit::door`
  drive the Python app from Rust screen tests. CI's `screens` job runs them. fwtest's flaky rerun still covers pytest
  only.
- P4 is in progress. On main, `flexweek-app::session` owns the request frame and its four workers, epochs, the 30 s
  limit, expiry and error words (#161, #163), busy/latest-ticket/status state (#164), autosave and leaving decisions
  (#167), and account flows including sign-in, registration, recovery, resume, sign-out, password and recovery-code
  changes and account deletion (#165, #166). `desktop/native/client.py` is a shell over
  `flexweek_engine.NativeCore`; the window still owns Qt callbacks, kept-session files, setup answers and week loading.
  Blocks, homework (#168) and study/protected hours (#178) are checked by the engine. The hours refusal is "Check the
  days and times of your study hours and protected time."
- CI moved to Depot on 2026-11-24 (#153). `.depot/workflows/verify.yml` runs `engine`, `verify-engine`,
  `verify-python`, `desktop`, `screens`, `rig`, `mutate` and `mutate-python`; mutation jobs run on pull requests and
  by hand. GitHub Actions keeps CodeQL and `.github/workflows/release-windows.yml`; #177 skips Windows installer builds
  for developer-build releases. Linux releases and developer builds run on Depot. `scripts/dev-release.sh` dispatches
  `dev-build.yml` from main; publishing normally takes about four minutes and replaces the GitHub `dev` pre-release.
- Recent fixes on main: the app icon is the dumbbell on a lime rounded square (#172); a working kept session no longer
  flashes the sign-in card (#173); Report a problem opens Jonathan's Google form with version and device details (#174);
  the Android pairing field keeps typed digits in order and draws the grouping space separately (#175). #179 updated
  the phone refusal tests to use the demo clock.
- Rust owns planning, storage, calendar rules and Qt-free desktop logic. Python still owns Qt/QML hosting, live week
  state and interface rules not yet ported, plus clock, environment and file integration. `backend/models.py` remains
  until P4 finishes. Python wrappers encode, call and decode rather than keeping a second implementation.
- Known gaps: Ctrl+wheel zoom in Material fails on Jonathan's Wayland desktop; Material memory growth remains
  unmeasured; Jonathan ran 1.5.0 on a real Windows PC on 2026-11-21, but the 2.0.0 rewrite's Windows pieces are not
  tried there; native AT-SPI delivery is unverified; the static audit's F1 and W3 are open; `fwtest flaky` lists the
  remaining flaky tests. The desktop drag tests in `test_material_drag_move_and_resize_blocks.py` can be clock-sensitive
  on CI.
- 2.0.0 follow-ups: `hypothesis` is installed and unused; Python store methods `apply_repeat_intents`,
  `delete_assignment`, `standing_blocks` and `save_assignment` have no app callers; five corpus generators still count
  any exception as a refusal. Known Rust/Python differences remain for integers past 64 bits, Python-only JSON values,
  estimates past 2^63 and a finished session with no start in `build_month`.

## Repo Landmarks
```
engine/engine/          pure Rust core: plan, solve, day, month, restore, desk modules; tests/ are the Rust twins
engine/sync/            iroh device sync (`flexweek-sync`)
engine/ffi/             UniFFI crate the Android app loads as libflexweek_ffi.so
engine/store/           Rust SQL helpers per table
engine/py/              PyO3 binding built as `flexweek_engine`
engine/mcp/             the `flexweek-mcp` server (stdio)
docs/engine/            contract.md, adapters.md (every wrapper's class), interface-logic.md
tools/fwtest/           Rust test runner: gate, mutate, rig, run, clean (contract docs/tooling/fwtest.md)
scripts/mutations/      mutation specs (JSON); engine cases point at `cargo:` tests
scripts/rig/            rig driver and plays for the hidden real-display session
engine/service/src/desk_requests.rs  the window's requests by method and /api/ path, answered in process
desktop/main.py         launcher: opens the saved data, phone sync if paired, then the native window
desktop/native/window.py     chrome, pages, dialogs, autosave, updater wiring
desktop/native/controller.py session: saves, solve, focus, alarms, reminders; now_ms is the clock
desktop/native/settings.py   the alarm dialog (the Widgets Settings and layouts/ were removed in 1.5.0)
desktop/native/material/     Material 3 shell: bridges (Python) and qml/ (views, week, hours/HoursPane, month)
desktop/native/look.py       packs, presets, palettes, the one stylesheet
desktop/native/version.py    VERSION, kept equal to the newest CHANGELOG heading
desktop/{build_*,package_*}  Linux and Windows builds; packaging/ holds AppImage, Inno, WiX
android/                the Android phone app (Kotlin + Compose)
desktop/tests/<area>/, backend/tests/  the Python suites by area (areas.toml in tools/fwtest); light_app.py, waiting.py
conftest.py             root: every test runs on backend/tests/fake_clock.CLOCK
.depot/workflows/       Depot CI: verify, dev-build, release-linux
.github/workflows/      GitHub Actions: codeql, release-windows (Windows installers only)
```

## Domain Model
SQLite: users → sessions, many dated weeks keyed (user_id, week_start), one preference row. Default desktop mode
uses a local per-user database (there is no hosted mode since 2.0.0's P2, D4); there is no automatic sync between
computers except device sync. The engine writes the database; device sync (`engine/sync`) and the phone bindings
(`engine/ffi`) write through their own connections, and the desktop opens it only read-only (to notice another
program's changes and a linked phone). Assignments are keyed (user_id, id) with a JSON body
and revision; a flexible block with `assignment_id` is a work session of that assignment. Routines are named
templates of locked blocks. Restore points snapshot an account's weeks and assignments. Recovery codes are hashed
and shown once. A format-3 export copies weeks, assignments, preferences and routines onto another account after a
preview. Recorded `operation_id` values make a retried write return the first result.

## Non-Obvious Decisions
- The engine core is pure: Python reads the clock, environment, files and randomness and passes them in.
- `serde_json` has `preserve_order` on and `engine/clippy.toml` forbids key-reordering removes, so stored JSON
  keeps Python's key order.
- Colour maths calls the C library's `cbrt`, `pow`, `atan2`, `sin`, `cos` at run time so results match Python's.
- Case folding uses a table generated from this interpreter, not a crate.
- The engine builds at opt-level 2 in debug so the solver's 150 ms budget holds under load (Jonathan's choice).
- A stored week's identity is its Monday; GET /api/week answers another calendar day as the week shown from that day
  (built from the two stored weeks it covers), not snapped to a Monday and not refused.
- The desktop app runs no server: requests are answered by the Rust service on worker threads in the app's process,
  so it opens no network port (phone sync listens only once a phone is paired). FLEXWEEK_*_ORIGIN are not read.
- Nuitka is called directly; `pyside6-deploy` rewrites its spec with machine paths.
- Windows installers: the Inno `AppId` and MSI `UpgradeCode` never change; Inno 7.1.0 is checksum-checked; WiX is
  pinned to 6.0.2. Linux leads with a tar.gz so the executable bit survives.
- The Material switch button keeps the label "Material 3" (Jonathan, 2026-11-06), not FIX-SPEC's "Back to Material".
- Developer build versions stay a timestamp because the updater orders builds by it; the commit goes in the kept
  copy's tag and title. The kept copy's tag points at the new run's commit, because the workflow token may not tag
  an older commit once main's workflows have changed (HTTP 403, 2026-11-06).
- CI rigs install no ffmpeg (the Ubuntu mirror hung on its libraries); the rig keeps frames and skips the video.
- The Android release key lives in `~/.config/flexweek-android/`, outside the repo; phone updates are signed with it.
- Material's P, Z and F keys have their own switch (`material.letters` in the look file), off for everyone; 1 to 5
  keep `material.shortcuts`, on by default. Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y and the zoom keys answer to neither.
- The assistant helper reads the clock on every call; `--now` holds one moment for tests, and a debug build also reads
  `FLEXWEEK_MCP_TEST_CLOCK_FILE` so a test can move a running helper's clock. The release build does not contain it.

## Session Handoff
- 2026-11-26: every PR opened 2026-11-25/26 is merged (#180-#197). Run log:
  `~/.flexweek-ui-harness/scratch/afk-2026-11-25/run.md`. Next: plan the rest of P4 (groups 6-9 after their first
  slices, then pydantic's adapters). Follow-ups: a split long task can take a 99-block week past 100 before the save
  refuses it (solver); an older phone app may drop `removed_days` when it re-saves a week; release-windows.yml and the
  Linux build container still install `stable` Rust. Three helper copies wait on Jonathan before deletion.
- 2026-11-24 (after the AFK run): #165, #166, #172-#176 merged; CI moved to Depot (#153); the hours windows are
  checked by the engine with a plain refusal (branch feat/p4-hours-windows). Next: group 2's save core with group 3
  (undo); Jonathan's picks from the Gemini redesign mockups (`~/.flexweek-ui-harness/scratch/design-2.0-richer/`).
- 2026-11-24 (AFK run, run sheet `~/.flexweek-ui-harness/scratch/rust-2.0.0/p4-afk-2026-11-24.md`): merged #163
  (requests through the Rust session), #164 (status), #167 (autosave, saving before leaving), #168 (block and
  homework checks by the engine) and #169 (strip parity), each after a Gemini 4 Neon PASS and green CI. Held for
  Jonathan as auth: #165 (sign-in, sign-up, recover, resume, sign-out in Rust) and #166 (password, recovery codes,
  account deletion), both reviewed (Gemini PASS on 4ed0c562 and a6f95261, and on their merge with main through
  #167); main was merged in again through #168 (a context.md conflict only, not re-reviewed); they do not have
  #169. Parked: the hours windows' refusal words (moving that check off pydantic changes what the status line says).
  A developer build from 635e7ba6 is in
  `~/.flexweek-ui-harness/scratch/rust-2.0.0/dev-build-p4/` (TRY-IT.md). Next: Jonathan's word on #165/#166 and the
  hours-window words; then group 2's save core with group 3 (undo), planned as one step since they share state.
- 2026-11-23 (after the AFK run; run sheet `~/.flexweek-ui-harness/scratch/rust-2.0.0/p3-p4-run-2026-11-23.md`):
  Jonathan's answers: pydantic in P4, one CI job for the Rust screen tests, the timeout words stay until P4, then
  "Finish P3 and start on P4". P3 finished in #160 (merged 00d5b41b, Gemini 4 Neon PASS round 2). P4's first PR,
  #161 (the frame), merged a9deb612 after Gemini round 3.
- 2026-11-23 (AFK run, run sheet `~/.flexweek-ui-harness/scratch/rust-2.0.0/afk-run-2026-11-23.md`): P2 parts 1-3
  merged (#154 670e4534, #155 b2b2f56a, #156 cd96e7f0), each after a Gemini 4 Neon PASS (rounds: 2, 3, 3) and green
  CI. P3 slice 1 (#158) merged ee90444e after Gemini round 3 and a confirmed CI fix (the door now reaches the window through the test helper). Held for Jonathan: #157 (spec.md), and #153 (Depot) from
  before. Parked: when pydantic goes, CI for the door tests, the sign-in timeout words ("its server"), the `gone`
  ledger rows (a choice to confirm). Facts the run met: `fwtest gate` takes its base from `VERIFY_BASE_SHA`, then the
  local `main` branch, then `origin/main` (`tools/fwtest/src/gate.rs`); it runs `ruff check .` with ruff's cache on;
  it does not run `cargo fmt --check`, which CI runs in engine and tools/fwtest.
  Next: Jonathan's answers, then P2's pydantic step or P4; P3's next slice (door setup steps for seeded data,
  more Week files, the CI step).
- 2026-11-20, branch `feat/material-only` (PR #141): released as v1.5.0 (see Current State).
