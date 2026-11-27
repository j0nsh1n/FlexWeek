# The FlexWeek engine in Rust

Status: E1–E7 are complete. This file keeps the original migration contract and its decisions. The
FastAPI server and `backend/app.py` mentioned below were removed in 2.0.0 P2. P4 then removed pydantic,
`backend/models.py`, and the adapters nothing imports any more. The window now asks the Rust service in
its own process. See `ARCHITECTURE.md`, `docs/engine/adapters.md` and `docs/engine/interface-logic.md`
for the current map.

FlexWeek's planning logic and its storage live in one Rust library, the engine. The desktop app keeps
its Material 3 Qt Quick/QML interface and Python bridges, and calls the engine through a Python module.
The Android app calls the same engine, so the week is planned and stored the same way on both.

Jonathan approved this on 2026-09-29, as one part of a larger decision: the tooling (fwtest) and the
engine move to Rust now, and the interface stays in Python and QML. The
reason is not speed. Measured on 2026-09-28, the planner takes 2 to 55 ms for real weeks, against a
150 ms budget. The reasons are one core for two apps, checks at compile time, and no garbage
collector freeing objects on the server's thread.

This file is the contract. The engine is built and reviewed against it.

## What moves

| Python today | Lines | Moves to | Slice |
|---|---|---|---|
| `backend/slots.py`, `backend/weeks.py` | 240 | `engine::time` | E1 |
| `backend/models.py` (the data, not the HTTP validation) | 660 | `engine::model` | E2 |
| `assignments.py`, `availability.py`, `comfort.py`, `day.py`, `month.py`, `explain.py` | 942 | `engine::plan`, `engine::day` | E2 |
| `restore.py`, `transfer.py`, `limits.py`, `recovery.py` | 162 | `engine::restore`, `engine::recovery` | E2 |
| `backend/solver.py` | 486 | `engine::solver` | E3 |
| `backend/storage.py` | 320 | `store` (SQLite) | E4 |
| `desktop/native/`: `weekmodel`, `calendar`, `focus`, `pomodoro`, `remind`, `reuse`, `history`, `files`, `tokens` (its colour maths), `update` | about 3,150 | `engine::week`, `engine::desk` | E5 |

What stays in Python and QML: `backend/app.py` (the FastAPI routes), the pydantic model classes in
`backend/models.py` as the checking layer at the HTTP edge and for `desktop/` (the engine's structs
are the data behind them, converted with `model_dump()` and `model_validate()` at the boundary),
the Material QML screens and every desktop Python module that imports Qt, the API tests, and the
interface's tests. The HTTP API does not change.

## Guarantees

1. **Nothing a student can see changes.** For every input, a ported function returns what the
   Python one returned. The HTTP API, its errors, and every word on screen stay the same, character
   for character: sentences the engine builds (explanations, labels, error messages) are compared
   exactly in the differential tests, numbers included, since Rust formats floats and durations
   differently from Python's `str()` unless told to.
2. **Every database keeps working.** The engine opens the same SQLite file, with the same schema and
   migrations. Every stored hash still verifies: passwords are
   `scrypt$32768$8$3$<salt>$<key>` (N 32768, r 8, p 3, 32-byte key, a 16-byte salt as hex), stored
   sign-in tokens are the SHA-256 hex of the token, recovery codes are SHA-256 of
   `flexweek-recovery:` plus the normalised code. A new sign-in token is URL-safe base64 of 32 random
   bytes without padding, as `secrets.token_urlsafe(32)` makes it. Test vectors come from the
   Python functions, and a database written by the Python store is read by the Rust one and the
   other way round. Migrations have one owner at a time: the Python store until E4 lands, the
   Rust store from then on; the other side never migrates.
3. **The app works after every slice.** A slice lands behind the Python function it replaces: the
   Python name stays, its body calls the engine, and the existing tests run unchanged. No slice
   leaves two live implementations of one function in the shipped app.
4. **The core is pure.** `engine` has no file, network, clock or randomness of its own. What it
   needs is passed in: the time now, the solver's deadline, and randomness for recovery codes and
   sign-in tokens. Only `store` touches the disk, and only the Python module touches Python.
5. **Parity is proven, not assumed.** Before a Python body is replaced, a differential test runs the
   Python and Rust versions on generated inputs (Hypothesis) and on every fixture the backend tests
   use, and requires equal outputs. Order is deterministic wherever it can show in a result: the
   engine iterates in the order Python does (insertion order for what Python keeps in a dict,
   stable sorts with the same keys), using `Vec` and `BTreeMap` or an explicit order, never a hash
   map's. The solver keeps Python's search order and is compared only on weeks that both versions
   finish in under half the 150 ms budget, since a week near the budget may run out of time on one
   side and not the other; a plan returned on running out of time is not compared.
6. **Errors keep their types.** Where Python callers catch `ValueError`, `LookupError` or a named
   error, the engine raises the same type with the same message.
7. **The solver lets other threads run.** During a solve, another Python thread waits no longer
   for its turn than it did under the Python solver, so the window stays responsive during a plan.
   A test measures it on a week that uses the whole budget. (Reworded on 2026-10-01 with Jonathan's
   approval: the search keeps the interpreter lock and reads the caller's clock through Python,
   which hands the lock round; releasing and re-taking it on every reading made a solve 12 times
   slower beside a busy thread.)

## Shape

```text
engine/                    a Cargo workspace at the repository root
  engine/                  crate `flexweek-engine`: the pure core, no I/O
  store/                   crate `flexweek-store`: SQLite through rusqlite, schema and migrations
  py/                      crate `flexweek-py`: the Python module `flexweek_engine` (PyO3, built by maturin)
```

Data crosses into Python as JSON text in the shapes the pydantic models already dump
(`model_dump()`); the Python wrappers encode and decode it, so `app.py` and `desktop/` keep their
types. Plain numbers, strings and occupancy lists cross as they are. (Changed on 2026-10-01 with
Jonathan's approval from "plain values": measured at about 0.02 ms for a 12-block week, and a
phone app calls the Rust types directly.) The engine's own types are Rust structs with serde,
named as the Python models are. The database connection is the exception: it hands Python rows
whose values are Python's own types, as `sqlite3` did.

## Building and checking

- `cargo fmt --check`, `cargo clippy --workspace -- -D warnings`, `cargo test --workspace` in
  `engine/`. These join spec.md's Validation list in slice E1, with Jonathan's approval as the
  fwtest checks were.
- `maturin develop --release` builds `flexweek_engine` into the checkout's `.venv`. The gate runs
  as today, with the differential tests added to `backend/tests/`.
- The PyInstaller builds ship the compiled module from E1 on, since from E1 the app calls it:
  `test_native_packaging` checks it is in the Linux and Windows bundles, and CI installs a Rust
  toolchain and builds the module on both, as the fwtest contract already requires for Linux.
- Pinned versions: the Rust toolchain in `rust-toolchain.toml`, crates in `Cargo.lock`, and
  maturin in `requirements-dev.txt`.
- Crates approved by Jonathan on 2026-10-01, where the code uses them: chrono, regex, sha2, hex and
  scrypt, beside PyO3, serde, serde_json and rusqlite. hmac and base64 stay only if still used once
  the storage slice is done. Approved on 2026-10-01 for E5: serde_json's `preserve_order` feature
  (it adds indexmap), so dicts keep the key order Python gave them. Approved on 2026-10-02:
  serde_json's `unbounded_depth`, used only where the binding reads text Python has already
  parsed, so a file nested past 128 levels reads as the original read it. Any other crate is
  asked for first. The Material scheme is not a new crate: it is a port of
  `@material/material-color-utilities` 0.3.0 (Apache-2.0) in `engine::material`, with the licence
  notice in `engine/engine/src/material/NOTICE`. `desktop/native/material/dynamic_color.py` calls
  that one function and reads Qt's palette accent. The accent stays in Python because the core
  does not import Qt. When the platform has not set the accent, the wrapper returns nothing.

## Slices

Each slice is one branch, reviewed and merged before the next starts, and ends with the gate green,
the new differential tests green, and the Rust checks passing.

- **E1, the frame and time.** The workspace, the Python module, `slots` and `weeks` ported, the
  differential test harness, and CI building and bundling the module on Linux and Windows. The
  Python `slots` and `weeks` call the engine.
- **E2, the model and the day's logic.** The data types, then `assignments`, `availability`,
  `comfort`, `day`, `month`, `explain`, `limits`, `restore`, `transfer` and `recovery`, in that
  order, each with its differential tests.
- **E3, the planner.** `solve`, `reschedule_after_miss` and `reschedule_running_late`, with the
  interpreter lock released during the search.
- **E4, storage.** `store` with the same schema, migrations, hashes, sessions and throttling. The
  backend API tests run against it unchanged, and the two stores read each other's files.
- **E5, the desktop's logic.** The modules in `desktop/native` with no Qt in them, which a Rust
  interface would otherwise rewrite: `weekmodel`, `calendar`, `focus`, `pomodoro`, `remind`, `reuse`,
  `history`, `files`, the colour maths in `tokens`, the checks in `custom_look`, and `update`. Same
  rules as E1 to E4. The week model and colour maths are called while the hours paint, so frame time
  is measured before and after (the 2026-09-28 figures were 1 to 9.5 ms) and must stay under 16 ms.
  Staying in Python and QML: `material/host.py`, `material/theme.py`, `material/dynamic_color.py`,
  `autostart.py`, `kept.py`, `tones.py`, and every module that imports Qt. `look.py` and
  `custom_look.py` remain adapters for stored look data; the Widgets look editor and design registry
  are gone.
- **E6, adapters only.** Data crosses the boundary as JSON text (see Shape), so the Python modules
  cannot simply be deleted: something has to encode the arguments and decode the answer. E6 makes
  each of them that and nothing more. A function in a moved module encodes, calls one engine
  function, and decodes; it does not branch on its data, default, clamp, sort or validate. Whatever
  logic the 2026-10-02 inventory found still in them (289 functions in 25 modules, 72 that never
  called the engine, 53 with branching) moves into the engine, and a test fails when a wrapper
  grows logic again. The pydantic classes stay in `backend/models.py`. Decided by Claude on
  2026-10-02 under Jonathan's overnight grant; to go back to the first wording, say "delete the
  wrappers".
- **E7, the map of logic left in the interface.** `docs/engine/interface-logic.md` maps the
  decision points in the small Python shell, `NativeSession`, Material bridges and QML, with their
  test areas. It replaces the old Widgets inventory after those modules are removed.

## Tests and tooling

Jonathan decided on 2026-09-30 that the overhaul covers everything but the interface, tests included,
and that the interface's own tests are tidied, in Python, once the ported tests are verified. The
reason is the full rewrite: whatever moves now stops growing in Python, so there is less to rewrite
later. The Python tests stay the check while code moves: a test is ported only once the code it
tests runs in the engine, so at no point are the code and its check rewritten together.

- **T1, the engine's tests.** The backend tests of logic and storage (not of HTTP routes),
  and the desktop tests that test E5's modules without Qt, become Rust tests in `engine/`, case for
  case; desktop tests that drive QML and the Python shell stay Python. Each keeps the Python test's
  expected values; none is re-derived from what the Rust code returns. A Python test is deleted only
  when its Rust version passes and catches the same faults: the mutation cases for moved code
  (backend and E5's modules) are pointed at the Rust source and run by `fwtest mutate`, which
  rebuilds the module for each one (no new tool; `cargo mutants` was the first idea), and every case
  the Python tests caught must still be caught. The differential tests are deleted last, since by
  then there is one implementation.
- **T2, the API tests, stay Python.** They test `backend/app.py`'s routes, which stay Python, and
  move with the server in the full rewrite.
- **T3, the rig.** `hidden_session.py` moved into `fwtest` in Rust (PRs 37 and 38): the hidden KWin,
  its private D-Bus, and stopping everything it started. `scripts/rig/drive.py` stays Python until
  the full rewrite, because it drives the PySide6 app from inside its process (Jonathan, 2026-10-01).
  Material's Day and Week rigs replace the design-specific runs.
- **T4, the interface's tests, tidied in Python, last.** It starts only once T1 to T3 are verified:
  the ported tests pass, catch every fault their Python versions caught, and the rig's counts match.
  Then shared helpers are merged, overlapping and slow tests cut, and the known flaky tests fixed.
  The interface's mutation specs stay.

## Planner settings

Amendment A4 adds five stored preferences and uses the existing study cutoff. The defaults are
today's planner, so an account saved before these columns plans the same week it did then.

| Control | Stored as | Default | What the planner does |
|---|---|---|---|
| Keep weekends homework-free | `weekend_homework_free` | off | Flexible homework is searched on Monday–Friday only. A locked weekend block stays. |
| Smart buffer | `buffer_min`, one of 0, 15, 30 | 15 | Empty minutes between scheduled tasks. The study cutoff and protected windows are not widened. Locked events already closer than the buffer are not moved. |
| Prioritize urgent deadlines first | `urgent_first` | on | On keeps the existing sooner-deadline order. Off, two tasks with the same room and priority are ordered by id. |
| Split long tasks | `split_long_tasks` | off | One cut of a flexible task longer than 60 minutes into two sessions that add up to it. The first session is the largest multiple of 15 minutes that does not exceed half, so 61 minutes becomes 30 and 31. A task that is already split, and a half whose id is already used, stays whole. This is not the focus timer: 25/5 can be saved with the split on. |
| Show weekends | `show_weekends` | on | Stored and synced. The planner does not read it. |
| Study window cutoff | `day_cutoff`, already in availability | unset | 20:00, 21:00 and 22:00 are the settings choices. The field still accepts the wider 15-minute grid. |

Each is its own preferences column and its own sync record, after `auto_split_pomodoro` and before
the two JSON preference records. A planner column still at the migration default stays unpublished
while the account has never saved settings. Saving settings sets `planner_settings_chosen`, so a
save back to the default is published even when it happens before the first sync. A later save back
to the default is published too. A phone that does not know a preference key quarantines that one
record and keeps applying the rest of the batch. Saving a split writes each half: its length, its
start, and its day. A half that did not fit is kept, with no start. The phone plan lists every half,
placed or waiting, under the original task's title, and accepting the plan keeps each half.
Python encodes the row, calls the engine, and decodes the trace. It does not decide where a block goes.

## Repeating blocks

Added 2026-11-12 (step 1 of the repeats rebuild, `scratch/repeats-design/REPEATS-DESIGN.md` option C).
School, Setup's activities and the student's weekly fixed times are repeats. A client never sends a
repeat's body: it sends what the student meant, as changes
(`flexweek_engine::repeats::Intent`):

```text
{"id": "school", "scope": "from", "from_date": "2026-11-09",
 "set": {"start"?, "duration_min"?, "title"?, "category"?},
 "add_days": [5], "remove_days": [2], "stop": false}
```

A new repeat is a change on nothing: `set` holds title, start and length, `add_days` its days. Storage
holds one standing row per repeat and Monday, and a copy of each repeat in every saved week, so a
change holds from its date's Monday. A weekly fixed time uses a `weekly-<id>` id and may carry an
inclusive `until` date in its body.

| Rule | Where |
|---|---|
| Patch a repeat; three-way merge of a later version or a week's copy (what it shared with the old repeat follows the new one, what it changed itself stays); words for a week's own changes, the notice, and the one-day note | `engine/engine/src/repeats.rs` |
| Weekly fixed times: standing blocks are Setup ids or `weekly-` ids | `flexweek_engine::desk::grid::is_standing_block` |
| Until: cut a block at its date when the week is read; restore the hidden days before comparing a week's copy; apply the same cut to shown-week changes | `standing::cut_at_until`, `standing::uncut_copy`, `standing::shown_with_standing`, `repeats::apply_to_week`, `shown::apply_repeats_to_shown_week` |
| Limit: at most 200 standing blocks at once; a repeat that starts standing counts every repeat it would stand beside, and imports count the most standing in any one week | `repeats::MAX_REPEATS`, `flexweek_store::apply_repeat_intents`, `standing::most_standing_at_once` |
| Apply changes: standing rows from that Monday (a later stop stays a stop), every saved week from that Monday on, the later weeks that kept their own change, and the notice in the account's 12- or 24-hour clock | `flexweek_store::apply_repeat_intents` (`engine/store/src/repeats.rs`) |
| Save handlers | `changes::apply` (assistant) and the app's `flexweek_service::changes::apply_changes` (`POST /api/changes`) both call that one function: the assistant after saving the batch's weeks, the app after its stored (Monday) weeks and before the first week shown from another weekday, or after every week when none is shown. The answer carries `repeats: {changed_weeks, kept, notice}`, plus `repeats.doubled_weeks` when a new weekly time doubles hand-made copies. A requested pre-change restore point is returned as `restore_point`. `engine/store/tests/fixtures/repeat_cases.json` runs through both. |
| Reads | `GET /api/week` and each week in the changes answer carry `repeats`, the bodies standing that week, when any stand |
| Desktop | The session edits `repeats` and sends the differences (`repeats::intents_between`); the open week changes at once by `repeats::apply_to_week`. Saving a weekly fixed time from this week on, or deleting a standing block this week and later, saves a restore point first, and the Material notice's Undo puts that point back. Copy last week's fixed times and Setup leave weekly fixed times alone. |
| Kept reminders | `desk::remind::{reminder_start_min, reminder_stays, reminder_snooze_until}` keep a reminder card until its block starts. Snooze waits five minutes, or until the start when fewer than five minutes remain. At the start the card goes and "starts now" takes over. |

## Not in scope

The interface stays in Python and QML, with its Python tests tidied in T4. The engine does not add
features: anything new goes in after E6, once there is one implementation to change.
