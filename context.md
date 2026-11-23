# context.md — FlexWeek

## Current State (2026-11-22)
- 2.0.0 (the Rust overhaul; plan `~/.flexweek-ui-harness/scratch/rust-2.0.0/plan/plan.md`) is under way on main,
  developer builds only until 2.0.0. P0 (#142) and P1 are merged: every route that reads or changes account data calls
  `flexweek-service` (Rust); health, timer presets, reminder limits and storage info still answer in Python.
  `backend/app.py` keeps HTTP, cookies and request checks; JSON saves hand the service the raw body, sign-in, sign-up,
  recovery and password change pass their parsed fields. P1 PRs: #143
  (one block check, Week and homework saves), #144 (routines, spread, repeat edits, Plan), #145 (the multi-week save),
  #146 (account export and import). Each move was compared with the old Python route over HTTP and against generated
  corpora (`engine/service/tests/fixtures`).
- Main had #140 (Material only, its own Qt Quick window, #118's weekly fixed times) and #137 (the phone 1.4.0 fixes)
  before 1.5.0. Done time is the larger of focus minutes and minutes ticked done (`plan::done_time`).
- Latest release: v1.5.0, published 2026-11-20 (US time) from main 0effa56f (PR #141). The previous release is
  v1.4.0 (2026-11-17); its Android app was signed with the same key as 1.3.0.
- Developer build `1.3.0.202611171825` (main 5788750) is `dev`; older builds stay as `dev-<commit>` pre-releases
  (`dev-18dee2e` the newest of them). GitHub publishes them; the Linux tarball can also be built here.
- In 1.3.0 since 1.2.0: FIX-SPEC 1.3 (#67-#76), the J lanes (Material Week zoom, Day hours, Month study fill, Look
  preview), the assistant's planning tools and live reload (#91, #92), the testing rebuild (#97, 2026-11-08: tests by
  area, light app, looks judged by review, CI as the gate), Material review fixes (#89-#96, #98-#105), CI/build work
  (#106-#109) and the release blockers from the 2026-11-10 review (#110, #112, #113, #114: developer-builds switch
  hidden off the tarball, the packaged smoke test opens Material, tag/version check, two flaky-test fixes).
- The 1.3.1 fixes (the assistant helper's clock, Material's letter keys, Help from the keyboard) are in 1.4.0; no
  1.3.1 is released.
- Checks: CI is the gate (Verify: engine, verify-python, both rigs, four desktop shards; mutation jobs on pull
  requests). CodeQL had 0 open alerts at the release review.
- Known gaps: Ctrl+wheel zoom in Material fails on Jonathan's Wayland desktop (parked probe in `scratch/ctrl-wheel`;
  named under Known limits in the 1.4.0 notes); Material memory growth (1.9 GB after 49 min, 2026-11-05) is unmeasured
  (also named there); Jonathan ran 1.5.0 (Material only) on a real Windows PC on 2026-11-21, and the rewrite's
  Windows pieces are not tried yet; native AT-SPI delivery is unverified; the static audit's F1 and W3 are open;
  `fwtest flaky` lists the tests still logged flaky; the assistant helper's stderr test
  (`engine/mcp/tests/hygiene.rs`) was changed in 606ad095 to wait for its line.
- 2.0.0 follow-ups after P1: the assistant's own batch save (`store::changes::apply`) does not take a week shown from
  another weekday and orders repeats differently from the app's (`service::changes`); the Python store methods
  `apply_repeat_intents`, `delete_assignment`, `standing_blocks` and `save_assignment` have no app callers;
  nine corpus generators still count any exception as a refusal
  (`make_transfer_corpus.py` was fixed); the desktop drag tests in `test_material_drag_move_and_resize_blocks.py` can
  fail on CI depending on the clock (passed on re-run, 2026-11-22).
- Rust (`engine/`, contract `docs/engine/contract.md`, wrappers `docs/engine/adapters.md`): planner and solver,
  slots, weeks, day, month, explain, restore, recovery codes, the store's SQL helpers and connection, and the
  desktop's Qt-free logic (`desk`). Python calls it through `flexweek_engine`; the wrappers only encode, call and
  decode.
- Python: the FastAPI routes (their bodies call the service and hold no SQL), password hashing's
  salt, the clock, environment and file reads, the pydantic checks, `backend/models.py`'s Spotify and due-date
  copies, `CATEGORIES` in `calendar.py`, `TYPE_PT` in `tokens.py`, `custom_look.readability`, all Qt drawing and
  `scripts/rig/drive.py`.
- Speed (pr35 review): placing the probe week 1.1 ms; drawing a frame of the hours 10.2 ms median (limit 16 ms).
- Known differences from the Python originals: integers past 64 bits and Python-only JSON (NaN, lone surrogates)
  in stored rows; an estimate past 2^63 raises `OverflowError`; `build_month` returns a month where Python raised
  `TypeError` on a finished session with no start. About 100 cases the deleted differential tests pinned have no
  Rust test (roadmap, carried over).

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
backend/app.py          FastAPI routes: account, session, ownership; serves no pages
desktop/main.py         launcher: starts the backend in-process, then the native window
desktop/native/window.py     chrome, pages, dialogs, autosave, updater wiring
desktop/native/controller.py session: saves, solve, focus, alarms, reminders; now_ms is the clock
desktop/native/settings.py   Widgets Settings (Look preview side by side from 1000 px)
desktop/native/layouts/      the Widgets designs; registry.py builds the dialog
desktop/native/material/     Material 3 shell: bridges (Python) and qml/ (views, week, hours/HoursPane, month)
desktop/native/look.py       packs, presets, palettes, the one stylesheet
desktop/native/version.py    VERSION, kept equal to the newest CHANGELOG heading
desktop/{build_*,package_*}  Linux and Windows builds; packaging/ holds AppImage, Inno, WiX
android/                the Android phone app (Kotlin + Compose)
desktop/tests/<area>/, backend/tests/  the Python suites by area (areas.toml in tools/fwtest); light_app.py, waiting.py
conftest.py             root: every test runs on backend/tests/fake_clock.CLOCK
.github/workflows/      verify, codeql, release packages, dev-build
```

## Domain Model
SQLite: users → sessions, many dated weeks keyed (user_id, week_start), one preference row. Default desktop mode
uses a local per-user database; hosted mode uses the configured deployment; there is no automatic sync between
them except device sync. The engine writes the database; device sync (`engine/sync`) and the phone bindings
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
- The desktop app runs the backend in-process on a pre-bound loopback socket (CSRF origin and TrustedHost pin one
  origin). An invalid FLEXWEEK_*_ORIGIN is an error, never a fall back to local.
- Nuitka is called directly; `pyside6-deploy` rewrites its spec with machine paths.
- The accent stays at least CIE76 distance 15 from every category colour. No test checks it since
  `desktop/tests/test_look.py` went with the Widgets styles in 1.5.0.
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
- 2026-11-22: 2.0.0 P1 finished; main a53767de. Every P1 PR had a Grok 4.7 review (PASS) and green CI before merge;
  stage branches and worktree leftovers are deleted. Next: P2 (no server), which needs Jonathan's answers to the
  plan's open decisions (plan.md section 10, D6 before P2's first candidate) and his approval of the spec.md wording
  (section 11) and the roadmap entry (section 12, not applied yet). Run log:
  `~/.flexweek-ui-harness/scratch/rust-2.0.0/afk-run-2026-11-22.md`.
- 2026-11-20, branch `feat/material-only` (PR #141): released as v1.5.0 (see Current State).
