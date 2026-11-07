# context.md — FlexWeek

## Current State (2026-11-06)
- Latest release: v1.2.0 (2026-10-27, tag `v1.2.0`, all ten assets and checksums verified); previous 1.1.1.
  Developer build 1.2.0.202611061702 is `dev` (main 33fe5eef); replaced developer builds stay as
  `dev-<commit>` pre-releases, never offered by the updater.
- On main since 1.2.0: FIX-SPEC 1.3 (#67-#76), CI speed-ups (#75), rigs without ffmpeg (#78), J23 Month study fill
  (#79), J21 Material Week zoom (#80), J25 Look preview side by side (#81), J22 Material Day hours (#82), developer
  builds kept by commit (#84).
- Checks: the last full gate (J22, before merge) passed 6031 tests, ruff and mypy; every PR's 13 CI checks passed.
  A timed full run takes 27 min wall, 80 min of test time over 3 workers, 74% of it in tests that start the
  whole app.
- Known failures: `test_placeholder_0185`, `test_regress_item0_time_boxes`, `test_week_hour_labels`,
  `test_setup_wizard`, `test_u19_week_list_row`'s fit cases, `test_layouts_window`'s 1024x640 Month card and some
  `test_material_window` / `test_material_focus` cases sometimes fail under load or with other files on the same
  worker and pass alone. The Windows release job builds again (#87, 2026-11-07); no tagged release has run yet.
- CI's `verify-python` runs the backend gate only; the desktop suite runs locally (R3.5 moves it to CI).
- Known gaps: Material memory growth (1.9 GB after 49 min on the tarball) is unmeasured; native AT-SPI delivery
  is unverified (Jonathan accepted the Qt accessibility tree); the static audit's F1 and W3 are open (roadmap).
- Testing rebuild: rules approved in spec.md (Validation & Tooling, "Testing structure"); phases in roadmap R3.
  R3.1 foundations on branch `test/r3-1-foundations`: one app clock (`backend/clock.py`, faked for every test by
  the root `conftest.py` at Thu 2026-11-05 19:00, guarded by `backend/tests/test_one_wall_clock.py`), a clean
  computer per test, one wait helper (`desktop/tests/waiting.py`) and the light app (`desktop/tests/light_app.py`);
  the Week files run on them. Draft, survey and timings: `~/.flexweek-ui-harness/scratch/testing-revision/`.
- Rust (`engine/`, contract `docs/engine/contract.md`, wrappers `docs/engine/adapters.md`): planner and solver,
  slots, weeks, day, month, explain, restore, recovery codes, the store's SQL helpers and connection, and the
  desktop's Qt-free logic (`desk`). Python calls it through `flexweek_engine`; the wrappers only encode, call and
  decode.
- Python: the FastAPI routes (about 40 SQL statements remain in `create_app`'s route bodies), password hashing's
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
desktop/tests/, backend/tests/  the Python suites (regress184/190 only with FLEXWEEK_REGRESS=1); light_app.py, waiting.py
conftest.py             root: every test runs on backend/tests/fake_clock.CLOCK
.github/workflows/      verify, codeql, release packages, dev-build
```

## Domain Model
SQLite: users → sessions, many dated weeks keyed (user_id, week_start), one preference row. Default desktop mode
uses a local per-user database; hosted mode uses the configured deployment; there is no automatic sync between
them except device sync. Only the engine opens the database. Assignments are keyed (user_id, id) with a JSON body
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
- A week's identity is its Monday; GET /api/week refuses a non-Monday rather than snapping it.
- The desktop app runs the backend in-process on a pre-bound loopback socket (CSRF origin and TrustedHost pin one
  origin). An invalid FLEXWEEK_*_ORIGIN is an error, never a fall back to local.
- Nuitka is called directly; `pyside6-deploy` rewrites its spec with machine paths.
- The accent stays at least CIE76 distance 15 from every category colour (`desktop/tests/test_look.py`).
- Windows installers: the Inno `AppId` and MSI `UpgradeCode` never change; Inno 7.1.0 is checksum-checked; WiX is
  pinned to 6.0.2. Linux leads with a tar.gz so the executable bit survives.
- The Material switch button keeps the label "Material 3" (Jonathan, 2026-11-06), not FIX-SPEC's "Back to Material".
- Developer build versions stay a timestamp because the updater orders builds by it; the commit goes in the kept
  copy's tag and title. The kept copy's tag points at the new run's commit, because the workflow token may not tag
  an older commit once main's workflows have changed (HTTP 403, 2026-11-06).
- CI rigs install no ffmpeg (the Ubuntu mirror hung on its libraries); the rig keeps frames and skips the video.
- The Android release key lives in `~/.config/flexweek-android/`, outside the repo; phone updates are signed with it.

## Session Handoff
- 2026-11-07, main 01a7e197 (#87 merged: Windows bundle check knows imagehlp.dll, Windows trims Qt's web modules).
  R3.1 on branch `test/r3-1-foundations` (worktree `~/.worktrees/flexweek-r3-1`), PR to open after rebase. Next:
  Jonathan approves the spec catch-up proposal (`~/.flexweek-ui-harness/scratch/r1/spec-catch-up.md`), then a
  tagged release to finish R1; R3.2 (Week rewrite) on his go. Logs: `~/.flexweek-ui-harness/scratch/r3-1/plan.md`,
  `~/.flexweek-ui-harness/scratch/r1/`.
