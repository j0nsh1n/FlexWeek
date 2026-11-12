# context.md — FlexWeek

## Current State (2026-11-10)
- Latest release: v1.3.0, published 2026-11-10 from main d61235ee (PR #111, the version bump). The Linux tarball and
  the Android APK were built on this computer (`scripts/build-linux-local.sh` in an Ubuntu 24.04 container; the APK
  signed with the 1.2.0 key); the AppImage and the Windows installers came from the tagged "Release packages" run.
  The previous release is v1.2.0 (2026-10-27).
- Developer build 4 (`1.3.0.202611101403`) is `dev`; older builds stay as `dev-<commit>` pre-releases (`dev-4e21fa5`
  and `dev-f242d2f` among them). GitHub publishes them; the Linux tarball can also be built here.
- In 1.3.0 since 1.2.0: FIX-SPEC 1.3 (#67-#76), the J lanes (Material Week zoom, Day hours, Month study fill, Look
  preview), the assistant's planning tools and live reload (#91, #92), the testing rebuild (#97, 2026-11-08: tests by
  area, light app, looks judged by review, CI as the gate), Material review fixes (#89-#96, #98-#105), CI/build work
  (#106-#109) and the release blockers from the 2026-11-10 review (#110, #112, #113, #114: developer-builds switch
  hidden off the tarball, the packaged smoke test opens Material, tag/version check, two flaky-test fixes).
- 1.3.1 is in progress on local branches cut from the v1.3.0 tag, not pushed: `fix/131-helper-and-keys` (the
  assistant helper's clock, Material's letter keys, Help from the keyboard) and `fix/131-material-week-sheets`.
- Checks: CI is the gate (Verify: engine, verify-python, both rigs, four desktop shards; mutation jobs on pull
  requests). CodeQL had 0 open alerts at the release review.
- Known gaps: Ctrl+wheel zoom in Material fails on Jonathan's Wayland desktop (parked probe in `scratch/ctrl-wheel`;
  named under Known limits in the 1.3.0 notes); Material memory growth (1.9 GB after 49 min, 2026-11-05) is unmeasured
  (also named there); no Windows package has been tried with Material on a real PC; native AT-SPI delivery is
  unverified; the static audit's F1 and W3 are open; `fwtest flaky` lists the tests still logged flaky; the assistant
  helper's stderr test (`engine/mcp/tests/hygiene.rs`) was changed in 606ad095 to wait for its line.
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
- Material's P, Z and F keys have their own switch (`material.letters` in the look file), off for everyone; 1 to 5
  keep `material.shortcuts`, on by default. Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y and the zoom keys answer to neither.
- The assistant helper reads the clock on every call; `--now` holds one moment for tests, and a debug build also reads
  `FLEXWEEK_MCP_TEST_CLOCK_FILE` so a test can move a running helper's clock. The release build does not contain it.

## Session Handoff
- 2026-11-12, branch `fix/replan-moves-missed-sessions` (#126) with `fix/planner-counts-minutes` (#125) merged in,
  local only. A missed session's minutes are counted through `this_weeks_part` against the saved week
  (`missed_minutes` takes `saved_week`), the desktop passes `_assignments_basis` to the solve request and to every
  count, and every count of minutes still needed reads the week with missed sessions stripped (`_open_week`). The
  "needs a time" count reads at `screen_point`, as `missed_block_ids` does, so a week that is over agrees with the
  missed sessions. Next: review of the merged branch.
- 2026-11-12, branch `fix/planner-counts-minutes` from main d7afedfe, local only. Done: a homework's time still
  needed is counted in minutes everywhere it is counted (engine `planning::time_still_needed_parts`,
  `uncovered_homework_minutes`); counts are exact minutes, and only what can be placed is rounded down to a
  quarter hour (Plan's rest session, a paste, a "Spread over days" share's `left`); the Plan notice, status
  line, Material drawer and More count name the minutes that have no time. Later weeks are read as the server's `planned_min` less the sessions of `saved_week` (the week that number was read with),
  which the desktop, the phone and the helper all pass; the desktop keeps the numbers it holds paired with that
  week after a failed Undo or Redo and an Undo of a delete (cases in `engine/engine/tests/test_minutes_count.rs`;
  redesign notes in `~/.flexweek-ui-harness/scratch/round2-fix2/planner-minutes/redesign/`). Not built: how
  the app asks the student what to do with such a remainder (options in
  `~/.flexweek-ui-harness/scratch/round2-fix2/planner-minutes/ASK-OPTIONS.md`, owner's pick pending). Next:
  review of this branch and the owner's pick.
- 2026-11-10, branch `fix/131-helper-and-keys` from the v1.3.0 tag: helper live clock, Material letter-keys
  switch, Help closing from the keyboard; the checks left from the 1.3.0 checklist are still open.
