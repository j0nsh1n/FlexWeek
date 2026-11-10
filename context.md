# context.md — FlexWeek

## Current State (2026-11-10)
- Latest release: v1.2.0 (2026-10-27, all ten assets and checksums verified). 1.3.0 is prepared on branch
  `release/1.3.0-prep` (version bump in `version.py` and Android, CHANGELOG heading dated 2026-11-10 and set again
  on release day, draft notes in `docs/release-notes-v1.3.0.md`, tag check and no-replace upload in the release
  workflow, release checklist in `docs/github-release.md`); not tagged.
- Developer build 3 (`1.2.0.202611100207`, main 8533105b) is `dev`; the two before it stay as `dev-4e21fa5` and
  `dev-f242d2f`. A Linux tarball can also be built on this computer in an Ubuntu 24.04 container
  (`scripts/build-linux-local.sh`, #108/#109); GitHub still publishes the builds.
- On main since 1.2.0: FIX-SPEC 1.3 (#67-#76), the J lanes (Material Week zoom, Day hours, Month study fill, Look
  preview), the assistant's planning tools and live reload (#91, #92), the testing rebuild (#97, 2026-11-08: tests by
  area, light app, looks judged by review, CI as the gate), Material review fixes (#89-#96, #98-#105) and CI/build
  work (#106-#109). The release review of main 1425ebb4 (2026-11-10) found it close to ready.
- Checks: CI is the gate. Verify on 1425ebb4 passed (engine, verify-python, both rigs, four desktop shards); the
  mutation jobs run on pull requests and passed on a by-hand run of 705bc0db. CodeQL has 0 open alerts. The Windows
  and AppImage packages were last built on 2026-11-07 (`fix/r1-release-unblock`), before most of the Material work.
- Known gaps (release review, 2026-11-10): the Get developer builds switch is shown on every install though only
  the Linux tarball has developer builds; the packaged smoke test never opens the Material window, and no Windows
  package has been tried with it; Material memory growth (1.9 GB after 49 min, 2026-11-05) is unmeasured; Ctrl+wheel
  zoom in Material fails on Jonathan's Wayland desktop (parked probe in `scratch/ctrl-wheel`); eight tests are logged
  flaky on main, two fail in the suite on nearly every run (list in the review report); the assistant helper's stderr
  test (`engine/mcp/tests/hygiene.rs`) can fail once; one Edit click in a Material block's menu is unchecked on a real
  screen; native AT-SPI delivery is unverified; the static audit's F1 and W3 are open.
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
desktop/tests/<area>/, backend/tests/  the Python suites by area (areas.toml in tools/fwtest); light_app.py, waiting.py
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
- 2026-11-10, branch `release/1.3.0-prep` from main 1425ebb4, not pushed. Done: version 1.3.0, tag/version check,
  no-replace uploads, release checklist, draft notes, context/roadmap/README brought up to date. Next, in the order
  of `docs/github-release.md`: hide the developer-builds switch off the tarball and add a Material step to the
  packaged smoke test (review B2, B3), a by-hand "Release packages" run on main, Material's memory measured for an
  hour (B4), Jonathan's call on Ctrl+wheel (S1), then the release pull request, his own try of a developer build,
  and the tag on his word. Report: `~/.flexweek-ui-harness/scratch/afk-2026-11-10/fable-release-review.md.report`.
