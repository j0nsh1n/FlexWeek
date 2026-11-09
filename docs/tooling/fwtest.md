# fwtest: the test harness

`fwtest` is one Rust command that runs FlexWeek's checks: the gate, the mutation checks and the
real-pointer rig. It replaces `scripts/verify.py`, `scripts/mutate.py` and the local
`run-alone.sh` queue. The 2,000-odd pytest tests stay in Python. `fwtest` only decides what runs,
when, with how much of the machine, and makes sure everything it started has stopped when it ends.

It exists because on 2026-09-28 the Python tooling froze the developer's displays. Gate runs back to
back used every core at full priority, and a rig's hidden KWin outlived its run by two hours. The
GPU driver stopped flipping frames under the load, and only a suspend brought the screens back.

This file is the contract. The implementation is built and reviewed against it.

## Guarantees

1. **Nothing outlives a job.** Every process a job starts, including grandchildren that detach or
   daemonize (KWin, Xwayland, dbus-daemon, a pytest worker), is stopped when the job ends. That
   holds whether the job ends normally, times out, gets Ctrl+C, or `fwtest` itself receives SIGTERM.
   If `fwtest` receives SIGKILL, the next `fwtest` run cleans up what it left.
2. **The desktop keeps priority.** A job runs at the lowest CPU priority (nice 19), with idle-only
   disk priority, pinned to at most half the machine's cores. Where a systemd user session exists,
   the job also runs in a transient scope with CPU and memory ceilings.
3. **One job at a time on the machine.** Jobs queue on one lock shared by every checkout, because
   the suites share Qt's test-mode files in `~/.qttest`. A job also waits for other agents' suites
   started outside `fwtest`, for up to 30 minutes.
4. **Source files are always restored.** A mutation's edit is undone however the run ends. A run
   that finds an edit left by a killed run restores it before it does anything else. A file under
   `engine/` also leaves a mark. The next clean rebuilds the installed engine module from the
   restored tree, so a killed run does not leave a mutated module either.
5. **Only its own processes are killed.** `fwtest` never matches processes by name or command line.
   It kills a PID only if the PID's start time matches the one it recorded.

## Commands

```text
fwtest gate [--backend-only | --touched [--base REF | --paths-from FILE]] [--workers N]
fwtest select [--base REF | --paths-from FILE]
fwtest mutate [SPEC.json ...] [--case NAME] [--engine-build COMMAND] [--no-engine-rebuild] [--engine-only] [--shard K/N]
fwtest rig [--server kwin|xvfb|auto] [ARGS FOR scripts/rig/drive.py ...]
fwtest run [--timeout SECONDS] [--touched [--base REF | --paths-from FILE]] -- COMMAND [ARGS ...]
fwtest flaky [--log FILE]
fwtest pictures render|compare|page|annotate|clips ...
fwtest clean
```

- `gate` runs the checks `scripts/verify.py` runs, in the same order: ruff, mypy over `backend`,
  pytest, then `git diff --check` on the working tree, the index, and the committed range from the
  diff base. The diff base is `$VERIFY_BASE_SHA`, then `main`, then `origin/main`, then `HEAD^`,
  skipping any value of all zeroes. Before the Python behavior step, the gate checks every case in
  `scripts/mutations/` that its `old` text occurs exactly once and that its `test` exists (a Python
  `path::function`, or a Rust `cargo:` test in an `engine/**/tests/` file). A miss fails the gate
  before any tests run. pytest gets `-n N` where N is `--workers`, or half the cores
  and at least 2. It prints `VERIFIED: Backend and desktop. Packaged binaries and other platforms
  need separate checks.` (or `VERIFIED: Backend.` with `--backend-only`) only when every step
  passed, as `verify.py` does. The per-step timeout is 2400 seconds; the desktop suite takes about
  15 minutes on 3 workers. pytest also gets `--junitxml` and `-o junit_family=xunit1`, so a failed
  test can be rerun alone (see [Flaky tests](#flaky-tests)).
- `gate --touched` runs the same steps on what the changed paths select (see
  [Test selection](#test-selection)): pytest gets only the selected paths, or no pytest step at all
  when nothing selected has pytest tests, and `cargo test --manifest-path DIR/Cargo.toml -p PKG ...`
  runs for each selected cargo workspace, after pytest. It prints the selection first, including
  the mutation cases the change touches, which it does not run. It ends with `VERIFIED: Touched
  areas only (AREAS); CI runs everything. ...` and never with the full-suite line. `--touched` does
  not combine with `--backend-only`. A full local gate is not needed before a push; CI is the gate.
- `select` prints what the changed paths select, without running anything: where the paths came
  from, how many changed, each path the map does not know, the areas, the pytest paths, the cargo
  packages by workspace, the mutation cases (spec and case name) and the picture areas.
- `mutate` runs every spec in `scripts/mutations/`, or the specs named. `--case` runs one case by
  name. `--engine-only` keeps cases whose file is under `engine/`. `--shard K/N` then keeps those
  whose 0-based index modulo N is K-1, after that filter and the existing spec-then-case order. K is
  1-based. N=1 is today's behaviour: every remaining case runs. The split is stable. Every case lands
  in exactly one shard. It prints one line per case (`RED`, `GREEN`, `BASE`, `PATTERN`, or `BUILD`, then the spec, the
  case name, and a short detail) and ends with `every mutation was caught` or `N mutation(s)
  SURVIVED`. `RED` is caught. `GREEN`, `BASE`, `PATTERN`, and `BUILD` each count as not caught. `BASE`
  means the case's test was red before any mutation (each test is run once unmutated per run, after
  a clean engine rebuild when a case left a mutated module installed), so the case proves nothing. It exits 1
  if any case was not caught. A file under `engine/` is rebuilt before its test. See
  [Mutating a file under engine/](#mutating-a-file-under-engine).
- `rig` runs `scripts/rig/drive.py` as one contained job. The job starts this checkout's hidden
  session after the stop handlers are installed, so the session is in the job's record and in the
  same scope and limits as the driver. The state file is written as each session process starts.
  `--server` is `kwin`, `xvfb`, or `auto` (the default: KWin when `kwin_wayland` is on `PATH`,
  otherwise Xvfb). That flag is not forwarded to the driver. The driver receives the display, the
  private D-Bus address, and the runs-folder key in its environment. The driver refuses that display
  or that bus when it is the one `fwtest rig` was started with. A display the session itself
  allocated is allowed, including `:0`. `FLEXWEEK_RIG_KEEP` is removed
  before the driver starts, and the run always stops the session afterwards by the PIDs recorded in
  its state file. `fwtest rig --list` does not start a session.
- `rig --play PLAY.json` runs the steps in a file instead of the fixed scenarios. See
  [Playing the app](#playing-the-app).
- `run` runs any command as a job, with the guarantees above. It exists for the picture tours and
  the one-off scripts that currently go through `run-alone.sh`. When the command is a pytest run
  (`... -m pytest ...`, or a program named `pytest`), `run` adds `--junitxml` to a temporary file
  unless the command names one, adds `-o junit_family=xunit1`, and reruns a failed test alone (see
  [Flaky tests](#flaky-tests)).
- `run --touched -- PYTEST COMMAND` adds the selected pytest paths to the end of the command and runs
  it at the checkout's top level, because the paths are relative to it. When the selection has no
  pytest tests it says so, runs nothing and exits 0. When it selects every area, the command runs
  as given (pytest.ini's testpaths). A command that is not a pytest run is refused with exit 2.
- `flaky` summarises the flaky-test log: one entry per test, most often logged first, then the most
  recent, with the last date, commit, where it ran and the first line of how it failed. `--log`
  reads another file, for example a log downloaded from a CI run.
- `pictures` draws the app's screens, compares two drawings, records the Widgets and Material flows as
  clips, asks a reviewer and builds the review page. See [Pictures](#pictures).
- `clean` stops every process recorded by a job that is no longer running. It also stops a hidden
  session whenever a job record or a state file names it, including when the job record is already
  gone and only the state file under `/tmp/flexweek-rig/` remains. That is how you stop a stranded
  session by hand. A live rig job in that checkout is left alone. It restores any source file left
  edited by a mutation run and removes the stale records. When `edits/engine-module.json` is
  present and no live job holds the checkout, it then runs the command stored in that mark and
  deletes the mark only after the rebuild succeeds. A failed rebuild leaves the mark, so the next
  clean tries again. It is safe to run at any time and does nothing when there is nothing to
  clean. Every other command runs it first.

Every command that runs Python uses `--python PATH` if given, then `$FWTEST_PYTHON`, then
`<checkout>/.venv/bin/python`, where `<checkout>` is the git top level of the working directory. A
git worktree has no `.venv` of its own, so give it a symlink to the main checkout's. If none of
these exists, `fwtest` says so and exits 2 rather than falling back to the system Python.

Exit codes: 0 when everything passed; 1 when a check failed or a mutation survived; 124 when a job
timed out; 75 when another suite outside `fwtest` held the machine for 30 minutes; 2 for a usage
error.

## Test selection

Spec.md's Testing structure rule 7: locally, only the tests for the area a change touches; CI runs
everything and is the gate. `fwtest select`, `gate --touched` and `run --touched` pick those tests
from the changed paths with the map in `tools/fwtest/areas.toml`.

The changed paths are, by default, every path that differs between the working tree and the merge
base of `HEAD` with `origin/main` (or `main` when there is no `origin/main`), plus untracked files
that are not ignored. A rename counts as both paths. `--base REF` compares with that ref's merge
base instead. `--paths-from FILE` reads the paths from a file, one per line, and does not ask git.
Without `--touched`, `--base` and `--paths-from` are a usage error (exit 2).

The map has three kinds of table:

- `[[area]]`: a set of tests. `tests` are pytest paths: a folder ends in `/`, and `*` in the file
  name matches any run of characters (`desktop/tests/test_*.py`). `cargo = { dir, packages }`
  names packages in one cargo workspace. `pictures = true` marks an area with picture screens. The
  picture areas are exactly the names in `desktop/tests/pictures/screen.py`'s `AREAS`, and each one's
  tests are `desktop/tests/<area>/`; a test checks both.
- `[[rule]]`: `paths` to `areas`, or to `everything = true`. A path pattern ending in `/` matches
  everything under that folder; otherwise it is one path, where `*` matches within one path part.
  The rules are tried in order and the first one that matches a path decides it. `areas = []` marks
  a path that no test checks (prose docs); it selects nothing.
- `[[also]]`: `paths` to `areas` added on top of the first matching rule. An also rule never makes
  a path known.

How the map reads:

- A path no `[[rule]]` matches selects every area. A change is never left with nothing to run
  because the map did not know a file. `select` names each unknown path, so the map can be updated.
- A test file selects its own area. A product file selects the areas whose behaviour it is mainly
  about. Shared plumbing (the window, the controller, the look, the backend's app and storage, the
  engine core and the store and binding) and the shared test foundations (both conftests, the light
  app, the wait helper, the fake clock, `screen.py`, the requirements) select every area.
- The `unmoved` area holds the desktop test files that are not in an area folder yet
  (`desktop/tests/test_*.py`, `regress184/`, `regress190/`). An also rule adds it for every change
  under `desktop/` and in the backend's own code, so they keep running while the area lanes move
  them. A pattern that matches nothing in the checkout is left out, so `unmoved` empties itself.
- When the selected areas have pytest tests but none of their paths exist yet, pytest runs the whole
  suite instead.
- A mutation case is touched when its spec file, its `file`, or the Python file its `test` names has
  changed, and every case is touched when every area is.
- Picture areas say which areas' screens may need drawing again. `fwtest pictures render --set
  touched` decides screen by screen from each screen's `sources`.
- No changed paths select nothing.

What CI does instead is every test: see [CI](#ci).

## Flaky tests

When pytest exits 1 in `gate` or in a pytest `fwtest run`, `fwtest` reads the JUnit report and runs
each failed or errored test again, alone (`python -m pytest -q -p no:cacheprovider NODE_ID` at the
checkout's top level, in the same job containment). A node id is built from the report's `file`
attribute, or from its dotted `classname` matched against the files in the checkout.

The rule: a test that passes alone is flaky. It is logged and printed (`FLAKY: ...`) and does not
fail the run. A test that fails again alone fails the run (`FAILED again alone: ...`). The run passes
only when every failed test passed alone. Nothing is rerun when pytest failed without naming a
failed test (a collection error), when it exited with anything but 1 (an interrupt, a usage error,
the job's timeout), or when more than 10 tests failed: that many is a break, not flakiness.
Mutation runs never rerun: a mutated test is meant to fail.

The log is JSON lines in `$FWTEST_FLAKY_LOG`, or `~/.flexweek-ui-harness/scratch/fwtest/flaky.jsonl`.
One line per flaky test:

```json
{
  "test": "desktop/tests/week/test_drag_a_block.py::test_a_dropped_block_keeps_its_length",
  "date": "2026-11-07T18:02:11Z",
  "commit": "<HEAD when it ran>",
  "place": "local",
  "how": "assert 3 == 4\nE   assert 3 == 4 ...",
  "beside": {
    "command": ".venv/bin/python -m pytest -q -n 8 ...",
    "tests_in_run": 412,
    "other_failures": []
  }
}
```

`place` is `local`, or `ci <job>` on GitHub Actions, where the flaky line is also added to the job's
summary. `how` is the failure's message and the start of its traceback, at most 2,000 characters.
`beside` is what else ran: the full command (its worker count and paths), how many tests the run
had and the other tests that failed in it. JUnit does not record which xdist worker ran a test, so
the log cannot name the tests that shared its worker.

## CI

`.github/workflows/verify.yml` runs on every push and pull request:

| Job | What | Shards |
|---|---|---|
| `engine` | builds the engine wheel and fwtest once | 1 |
| `verify-engine` | fwtest's and the engine's `cargo fmt --check`, `clippy -D warnings`, `cargo test` | 1 |
| `verify-python` | `fwtest gate --backend-only`: lint, types, mutation patterns, backend tests, diff checks | 1 |
| `desktop` | every test file under `desktop/tests` and `scripts/rig`, offscreen, through `fwtest run` | 4 |
| `rig` | the real-pointer rig, Day and Week, under Xvfb | 2 |
| `mutate` | the mutation cases under `engine/` (pull requests and by hand) | 4 |
| `mutate-python` | every other mutation case (pull requests and by hand) | 6 |
| `pictures` | the touched screens, before and after (see the pictures section) | |

The desktop shards deal the sorted test files out in turn. Each test-running job sets
`FLEXWEEK_SILENT=1`, and the Python jobs upload their flaky log as an artifact (`flaky-*`, kept 30
days) when there is one. `mutate-python` copies the specs without their engine cases into the
runner's temporary folder, because `fwtest mutate` has `--engine-only` and no opposite. Expected
wall time for a pull request: about 30 to 40 minutes, most of it the engine build followed by the
desktop and mutation shards running side by side; the engine mutation shards are the longest.

## Playing the app

`fwtest rig --play PLAY.json [--out DIR]` lets an agent use FlexWeek the way a student does. The rig starts
the app on its hidden desktop (never the developer's display or bus), signs in a throwaway account against
a local server, holds the clock, and then does what the file says with the real pointer and keyboard
(xdotool, as the scenarios do). It records what the screen showed after each step. `--play` does not
combine with `--design`, `--tab`, `--scenario`, `--option` or `--list`. The sound is off.

A play file is JSON, with `setup` (all of it optional) and `steps`:

```json
{
  "setup": {
    "clock": "2026-10-15T17:00",
    "seed": "rig",
    "size": [1280, 800],
    "design": "classic",
    "clock_24h": false,
    "text": "normal",
    "look": "terminal"
  },
  "steps": [
    {"click": "objectName"},
    {"click": [640, 300]},
    {"click": {"text": "Button words"}},
    {"double_click": "objectName"},
    {"right_click": "objectName"},
    {"drag": ["objectName", [700, 420]]},
    {"type": "words"},
    {"key": "shift+Tab"},
    {"wait": 500},
    {"advance_clock": 30},
    {"shot": "label"},
    {"tree": "label"},
    {"say": "a note for the log"},
    {"see": "School"}
  ]
}
```

Setup:

| Key | Meaning | Default |
|---|---|---|
| `clock` | Local time the clock is held at, `YYYY-MM-DDTHH:MM`. The week shown is that date's week. | Thursday 15:40 of the current week, as the scenarios use |
| `seed` | `rig`: the scenarios' week (School, Soccer, three homework items). `setup-done`: a new account that skipped Setup, so an empty week with the defaults. `empty`: a new account on the first Setup page. `material-new`: Material is the saved surface and nobody is signed in, so the play starts on the Material sign-in card. | `rig` |
| `size` | Window size in pixels, 640x480 up to 3840x2160 | `[1280, 800]` |
| `design` | Any rig design (`classic`, `timeline`, `mission`, `bento`, `retro`, `clay`) or a My day screen (`one`, `dial`; shown on the My day tab) | `classic` |
| `clock_24h` | The 24-hour clock. Ignored for `empty`, where Setup asks. | `false` |
| `text` | `normal` or `large` text | `normal` |
| `look` | A look preset (`high-contrast`, `paper`, `ink`, `terminal`, `poster`, `pastel`) or a theme pack (`system`, `light-frost`, `dark-frost`, `nocturne`, `slate`). Ignored for the pack when `seed` is `empty`. | the pack's own |
| `mode` | `light` or `dark`. Used with `material-new` for Material's own light/dark. | `light` |
| `motion` | `on` (the app's Normal animations) or `off` | the account's own |
| `record` | Record the play as a clip: PNG frames and, with a GPU encoder, a video (see [clips](#clips)) | `false` |

Steps, each an object with one action:

- A target is an `objectName`, a point `[x, y]` in window pixels, or `{"text": "Button words"}`, which
  matches a button, a label, an accessible name or a menu row by the words a student reads (case and a
  trailing "..." do not matter; an exact match wins over a partial one, then the topmost, leftmost).
  A menu or dialog that is still opening is waited for, up to 2 s.
- `click`, `double_click`, `right_click`: move the pointer onto the target, press and release.
- `drag`: `[from, to]`, each a target. Press, travel in steps, let go.
- `type`: the words, typed key by key into whatever has the keyboard focus. A newline presses Return.
- `key`: one xdotool key name or combination: `Tab`, `shift+Tab`, `ctrl+z`, `Escape`, `Return`, `space`.
- `wait`: milliseconds, up to 60000.
- `advance_clock`: minutes. Moves the held clock forward and runs the app's reminder, focus-timer and
  layout timers once, so what changes with the time shows up now.
- `shot`: PNG of the window, and one more of each open dialog or menu.
- `tree`: JSON of every visible widget: class, `objectName`, `accessibleName`, `accessibleDescription`,
  text, geometry in window pixels, enabled, has focus, checked; menu rows too. It also names the focused
  widget and the open dialog. Password boxes show `(hidden)`.
- `say`: a note in the log.
- `see`: the words or an `objectName` that must be on screen, including a QML item. The rig finds QML
  by walking visual children and uses the item's real position. A QML item clipped away by a parent
  or the window is not seen or clicked, and a click lands in the visible part. A miss is `NOT DONE`.

Every step writes one line to `DIR/log.txt`: what it did, where the pointer went, the widget with focus,
the open dialog and the open menu. A step that cannot be done (no such widget or text, a dialog in the
way, xdotool failing) logs `NOT DONE` and why, and the play goes on. The play exits 1 when any step was
not done. A final shot and tree are always
taken. The play file is checked before the session starts, and every mistake in it is named with its step
number. Files are numbered by step (`04-after-tab.png`, `04-after-tab.json`); a dialog or menu gets the
class name added to the shot's name. `DIR` is `~/.flexweek-ui-harness/scratch/plays/<time>-<play name>/`
unless `--out` names it.

Example: a new account that skipped Setup, Add fixed time, type a title, Tab, look at the result.

```json
{
  "setup": {"seed": "setup-done"},
  "steps": [
    {"click": "addArrow"},
    {"key": "Escape"},
    {"key": "space"},
    {"click": {"text": "Add fixed time"}},
    {"type": "Band practice"},
    {"key": "Tab"},
    {"shot": "after-tab"}
  ]
}
```

The `Escape` then `space` after the click is deliberate. On a fresh window the first click on a menu
button sometimes only focuses it (cause not found), so the keyboard opens the menu either way.

## Pictures

Looks are checked with pictures, not in code (spec.md, Testing structure, rule 6). Three pieces work
together:

- **Screens.** Each area declares the screens worth a picture in
  `desktop/tests/pictures/screens_<area>.py` (a lane may split one area over several files,
  `screens_<area>_h<N>.py`). Each is a `Screen` from `desktop/tests/pictures/screen.py`: an id, a
  `prepare` that puts a light window in the state to photograph, the `checks` the reviewer makes,
  and the product `sources` whose change means the screen is drawn again.
- **The renderer**, `scripts/pictures/render.py`. It is Python because it draws Qt. It draws every
  declared screen in every variant in one fixed setup and writes the PNGs and `index.json`.
- **`fwtest pictures`**, in Rust. It picks the screens a change touches, runs the renderer as a
  contained job on this checkout and, to see what a branch changed, on another ref, compares the two
  drawings, asks a reviewer, records the flows as clips, and builds the review page.

```text
fwtest pictures render --set full|touched [--base REF] [--changed FILE] [--out DIR] [--timeout SECONDS] [--python PATH]
fwtest pictures compare BEFORE AFTER --out DIR [--tolerance N] [--min-pixels N]
fwtest pictures page COMPARE [--clips DIR]
fwtest pictures annotate COMPARE --reviewer COMMAND [--timeout SECONDS]
fwtest pictures clips [--flow NAME] [--out DIR] [--python PATH]
```

What a branch changed, by hand:

```sh
fwtest pictures render --set touched --out ~/.flexweek-ui-harness/scratch/pictures/my-pr
fwtest pictures compare ~/.flexweek-ui-harness/scratch/pictures/my-pr/base \
  ~/.flexweek-ui-harness/scratch/pictures/my-pr/head --out ~/.flexweek-ui-harness/scratch/pictures/my-pr/compare
fwtest pictures page ~/.flexweek-ui-harness/scratch/pictures/my-pr/compare
```

`render` prints the compare and page lines with the right folders when it finishes. Open
`compare/index.html` in a browser.

### Which screens are drawn

- `--set full` draws every screen, on this checkout only unless `--base` is given.
- `--set touched` draws the screens the changed paths touch, on this checkout and on the base
  (`--base`, default `origin/main`). The changed paths are git's: everything changed since this
  branch and the base parted, plus changes in the working tree and untracked files. `--changed FILE`
  gives them instead, one per line.
- A changed path touches a screen when it is, or lies in a folder that is, one of the screen's
  `sources` or the screen's own screens file. A path touches every screen when it is something every
  picture is drawn from: `scripts/pictures/`, `screen.py`, `light_app.py`, `waiting.py`,
  `window_support.py`, `backend/tests/fake_clock.py`, `desktop/tests/fontconfig.conf` or
  `desktop/assets/fonts/`. So does any other file in `desktop/tests/pictures/`, because it is a
  helper some screens files import and the listing cannot say which.
- When nothing is touched, the renderer is not started (it would still cost a sign-up), and the side
  gets an `index.json` with no pictures.

### How `render` runs

Each side is one contained job, with everything in [How a job is contained](#how-a-job-is-contained):
the machine-wide lock, nice 19 and the caps. `--timeout` stops a side after that many seconds
(default 3600, exit 124). The base is checked out in a detached worktree under
`~/.flexweek-ui-harness/scratch/pictures/worktrees/` and removed afterwards. It is drawn with this
checkout's renderer and this checkout's Python, so both sides are drawn the same way and share one
installed engine module. The output folder (default
`~/.flexweek-ui-harness/scratch/pictures/<time>-<pid>/`) holds `head/`, `base/` and `changed.txt`.
The exit code is the worse side's. The renderer exits 1 when any picture failed or a screens file
could not be read.

### The fixed setup and the variants

Every picture is drawn offscreen (`QT_QPA_PLATFORM=offscreen`), silent (`FLEXWEEK_SILENT=1`), with
grey-shade text (`FONTCONFIG_FILE=desktop/tests/fontconfig.conf`) and the bundled fonts, under a home
folder of its own so Qt's test files are never a test run's. Before each picture, and again after
it, the computer is made clean the way the desktop conftest does it between tests: the clock goes back
to `fake_clock.START` (Thursday 2026-11-05 19:00), the 24-hour clock is set again, and the look file
and the week-start file are removed. Each picture opens a light window on a fresh copy of the one
signed-up account, so preferences a screen saved in `prepare` are gone for the next one. Animations
are off, so nothing is caught halfway through a fade. Screens never reach Spotify or the browser.

The variants of one screen:

| Set | Styles | Mode | Text | Size | High contrast |
|---|---|---|---|---|---|
| every screen | each style | light and dark | Normal | 1280x800 | no |
| `main` screens, also | each style | light | Large | 1024x640 | yes |

The styles are every Widgets design of the screen's role (the main views; the day screens for a My
day screen), in the layouts registry's order, then Material 3. A screen's `styles` narrows them:
design ids (`"classic"`), `"material"`, and `"widgets"` for every Widgets design of its role. An
unknown style is reported as that screen's error. Light and dark are the `light-frost` and
`dark-frost` packs on Widgets, and Material's own mode on Material 3.

A picture is `<out>/<screen id>/<style>.<mode>.<text>.<width>x<height>[.hc].png`, for example
`week.grid/classic.dark.normal.1280x800.png`.

### index.json

```json
{
 "version": 1, "set": "touched", "root": "/path/to/checkout", "commit": "<sha>",
 "problems": [{"module": "desktop/tests/pictures/screens_week.py", "error": "<traceback>"}],
 "pictures": [{
  "screen": "week.grid", "area": "week", "module": "desktop/tests/pictures/screens_week.py",
  "main": true, "checks": "...", "sources": ["desktop/native/hours"],
  "variant": "classic.light.normal.1280x800", "style": "classic", "mode": "light", "text": "normal",
  "size": [1280, 800], "high_contrast": false,
  "picture": "week.grid/classic.light.normal.1280x800.png",
  "measurements": {"labels": [], "focus": {}},
  "error": null
 }]
}
```

- `problems` are screens files that could not be imported, entries that are not a `Screen`, ids
  declared twice, and ids chosen for `touched` that no file declares.
- A picture whose `prepare` (or drawing) raised has `picture: null` and the traceback in `error`. It
  is never left out.
- `measurements.labels`: every visible label, button and Material 3 `Text` with words, with its
  rectangle in the picture, `too_wide` (the words need more room than the widget has: a size hint
  wider than the widget, a word-wrapped label taller than its height, a QML text that is truncated;
  `null` for rich text), and the text contrast. The contrast is read from the picture: the colour most
  of the rectangle is (what the words sit on) against the colour that stands out from it most (the
  ink). It is a measurement to look at, not a verdict. The page flags anything under 4.5:1.
- `measurements.focus`: the widget (or QML item) that has keyboard focus, and `ring`, whether it draws
  differently without focus. The picture is taken again with focus removed and the pixels compared
  in the widget's rectangle grown by 4 px, since a ring is drawn just outside a control as often as
  inside it.

### compare

`compare` matches the two folders' pictures by screen and variant. Two pixels are the same when no
channel differs by more than `--tolerance` (default 24 of 255), which absorbs the anti-aliasing noise
of text drawn twice. A picture has changed when more than `--min-pixels` (default 8) pixels are not
the same. A picture whose size changed is changed, with no difference image. Each picture is
`failed` (either side could not draw it), `changed`, `added`, `removed` or `unchanged`. Only the
pictures that are not unchanged are copied into `--out` (`before/`, `after/`, and `diff/` with the
differing pixels marked), beside `compare.json`, so the folder carries what the page shows and nothing
more. It exits 1 when the after side failed to draw something or had a problem.

### page

`page` writes `index.html` into the compare folder. Failed pictures come first, then changed (most
pixels changed first), added and removed, each with before, after and the difference, the screen's
checks, the reviewer's notes when `annotate` ran, and the measurements. Unchanged pictures are listed
by name only. With `--clips`, each clip is shown as a strip of 8 PNG frames picked evenly from first
to last, with the video linked beside it. Everything the page shows is copied into the compare folder,
so the folder is uploaded as it is.

### annotate and writing a reviewer

`annotate` runs a reviewer command once for each changed or added picture, keeps what it prints in
`review/<screen id>/<variant>.txt`, and the page shows it under the picture. Run `page` again
afterwards. `fwtest` ships no reviewer and calls no model, and CI runs no reviewer. Kimi K3.1 Pro
(T3 provider `acpRegistry_kimi`) is the planned annotator, and Gemini or Claude decides (spec.md,
Testing structure, rule 6). Whoever runs the review passes the command.

A reviewer is any shell command, run with `sh -c` in its own process group. For each picture it gets:

- the request as JSON on its standard input, and the same JSON in the file named by
  `FWTEST_REVIEW_REQUEST`:
  `{"screen", "variant", "status", "checks", "before", "after", "diff", "measurements"}`, where
  `before`, `after` and `diff` are absolute PNG paths or `null`;
- the same facts in `FWTEST_SCREEN`, `FWTEST_VARIANT`, `FWTEST_STATUS` (`changed` or `added`),
  `FWTEST_CHECKS`, `FWTEST_BEFORE`, `FWTEST_AFTER` and `FWTEST_DIFF` (empty when there is no such
  picture).

What it prints on standard output is the answer, kept as plain text. Exiting non-zero, printing
nothing, or running past `--timeout` (default 300 seconds; the whole process group is stopped) leaves
a "Reviewer failed: ..." note in place of the answer, and `annotate` exits 1 after asking about the
rest. A minimal reviewer that only lists what the measurements flag:

```sh
#!/bin/sh
# review-measurements.sh: a stand-in reviewer for trying annotate without a model.
jq -r '"Checks: \(.checks)",
  (.measurements.labels // [] | .[] | select(.contrast != null and .contrast < 4.5)
    | "Low contrast \(.contrast):1 on \(.text)"),
  (.measurements.labels // [] | .[] | select(.too_wide == true) | "Too wide: \(.text)"),
  (if .measurements.focus.ring == false then "No focus ring on \(.measurements.focus.focused)" else empty end)'
```

```sh
fwtest pictures annotate COMPARE --reviewer ./review-measurements.sh
```

A model reviewer does the same: it reads the request, sends the `before`, `after` and `diff` PNGs with
the checks to the model, and prints the model's notes.

### clips

`clips` records the flows that must behave the same in Widgets and Material 3, on the rig's hidden
desktop: add homework, tick done and Undo, open and edit, drag a block, Plan my homework, Running
late, start and finish Focus, switch Day / Week / Month, and change the look in Settings. Each flow
is a play file per surface, `scripts/rig/flows/<flow>.widgets.json` and
`scripts/rig/flows/<flow>.material.json`, in the format of [Playing the app](#playing-the-app). Each
file is played twice, with animations on and off, each run one `fwtest rig --play` with the play's
setup given `"motion"` and `"record": true`. `--flow NAME` records one flow. A whole run is 36 rig
runs, so it is heavy: run it once, when the flows or what they cover changed.

A recorded run keeps PNG frames of the window, ten a second, with the pointer drawn as a red dot, in
`<run>/frames/`. It also keeps `<run>/clip.mp4` when the computer can encode on the GPU (`ffmpeg` with
`h264_vaapi` on `/dev/dri/renderD128`). Without either, it keeps the frames only and says why; it never
falls back to a slow CPU encode. The output folder (default
`~/.flexweek-ui-harness/scratch/pictures/clips/<time>-<pid>/`) lists every run in `clips.json`, which
`page --clips` reads. The exit code is the worst run's.

### Where pictures are used

Pictures are a local review aid. They are drawn and looked at on this machine by the visual reviewer,
never in CI and never on a pull request: CI runs tests only, and no test reads a picture. Clips are
recorded locally too.

## Data

Everything `fwtest` keeps between runs lives in `~/.flexweek-ui-harness/fwtest/`, outside every
checkout.

```text
lock                   the machine-wide lock (flock)
jobs/<job id>.json     one record per running job
edits/<file hash>.json one record per source file a mutation is editing
edits/engine-module.json  the command that rebuilds a clean engine module
logs/<job id>.log      the job's combined output
```

A job record:

```json
{
  "id": "20260928-061500-4242",
  "checkout": "/home/jonathans/FlexWeek",
  "argv": [".venv/bin/python", "-m", "pytest", "-q", "-n", "8"],
  "started": "2026-09-28T06:15:00Z",
  "owner": {"pid": 4242, "start_ticks": 912345},
  "processes": [{"pid": 4250, "start_ticks": 912360, "comm": "python"}],
  "limits": {"nice": 19, "io": "idle", "cpus": [0, 1, 2, 3, 4, 5, 6, 7], "timeout": 600}
}
```

`start_ticks` is field 22 of `/proc/<pid>/stat`. A process is "ours" only while its PID and start
ticks both match. `processes` is refreshed as the job runs. A job is stale when its owner PID no
longer matches its start ticks.

A mutation edit record:

```json
{"file": "desktop/native/look.py", "backup": "<absolute path of the copy>", "case": "look/…"}
```

The backup is written, and the record saved, before the edit is made. The source is restored from
the backup and the record deleted after the case's test finishes, whatever the outcome.
`restore_finished` skips `engine-module.json`. That file is not an edit record.

```json
{
  "checkout": "/path/to/checkout",
  "command": [".venv/bin/maturin", "develop", "--release", "--manifest-path", "engine/py/Cargo.toml", "--features", "audit"]
}
```

The mark is written before a mutated engine build and removed only after a clean rebuild succeeds.

A mutation case stays as `scripts/mutate.py` reads it, with two optional fields:

```json
{
  "name": "…",
  "file": "path from the repo root",
  "old": "…",
  "new": "…",
  "test": "pytest node id",
  "expect": "",
  "features": []
}
```

`expect` is omitted, or `""`, when the catch is a failing pytest. `"build"` means a failed engine
rebuild is the catch. Any other value is `PATTERN` and the file is not edited. `"build"` on a file
outside `engine/` is also `PATTERN`. `features` lists cargo features added only to the mutated
build, for example `["audit"]`. The clean rebuild does not pass them.

Running a case: check `old` occurs exactly once, save the edit record, write the edited file,
delete the file's cached bytecode (`__pycache__/<stem>.*.pyc`, because a same-length edit within a
second can reuse a stale `.pyc`), run `python -m pytest <test> -q -x -p no:cacheprovider` with
`PYTHONDONTWRITEBYTECODE=1` and `QT_QPA_PLATFORM=offscreen`, restore the file, delete its bytecode
again, delete the record. A case is caught when pytest exits non-zero.

A case may name a Rust test instead of a pytest node id:

```text
cargo:<package>:<test target>:<test name>
```

For example
`cargo:flexweek-engine:test_solver:test_a_low_session_skips_midnight_when_the_morning_is_free`.
`fwtest` runs this in `<checkout>/engine`:

```text
cargo test -p <package> --test <target> -- <test name> --exact
```

Cargo compiles the mutated source, so this case does not rebuild the Python module.
The source file is still restored when the case ends. A compile failure is `BUILD`
and is not caught, unless the case sets `"expect": "build"`. A failing assertion is
`RED`. A `cargo:` value that is not those three fields is `PATTERN`, and the file
is not edited.

## Mutating a file under engine/

A case whose `file` has `engine` as its first path component edits Rust that the installed
`flexweek_engine` module was built from. Pytest imports that module, so the edit is invisible
until the module is rebuilt. `engines/` is not an engine path.

For each such case `fwtest`:

1. Saves the edit record and writes the mutation, the same way it does for Python.
2. Writes `edits/engine-module.json` with the base install command, before the build.
3. Runs that command with the checkout as its working directory. The case's `features` join
   the command's `--features` list. The default command is
   `<checkout>/.venv/bin/maturin develop --release --manifest-path engine/py/Cargo.toml --features audit`.
   `FWTEST_ENGINE_PROFILE` replaces `--release` with `--profile <name>` on that default command,
   for both the mutated build and the clean rebuild, so caught/missed compare like with like. A
   mutant is caught or not by the tests, which do not depend on optimisation. The default stays
   `--release`. Before the first mutated build, `fwtest` asks the checkout's Python whether
   `flexweek_engine` has `panic_probe`. When it does not, the command stored for the clean
   rebuild omits `--features audit`, so the checkout is left as it was found. When the import
   cannot be read, the clean rebuild keeps `--features audit`. A command given with
   `--engine-build` or `FWTEST_ENGINE_BUILD` is used as given and is not probed.
4. Runs the case's pytest, unless `test` is a `cargo:` name. That case skips this
   rebuild and the one in step 3. A pytest case that built prints `built in Ns` on its line.
5. Restores the source from the saved copy.
6. At the end of the spec, runs the clean command again and deletes the mark. The same clean
   rebuild runs before a later case whose file is not under `engine/` when the mark is still
   there. Stderr prints `rebuilt clean engine module in Ns`. The mutated build still passes
   `--features audit` when the default command is in use.

A build that fails is `BUILD`. The detail starts with `did not build`. The case is not caught.
When the case sets `"expect": "build"`, that same failure is `RED` and the detail still starts
with `did not build`. A failure to write the mark is `GREEN`, the same as a failure to write the
backup.

`--engine-build COMMAND` replaces the install command. `FWTEST_ENGINE_BUILD` does the same when
the flag is absent. The value `off`, the flag `--no-engine-rebuild`, or `FWTEST_ENGINE_REBUILD`
set to `0`, `off`, or `false` skips the rebuild. The source is still edited and restored, and
pytest runs against the module already installed, so the case is not caught. The command is a
shell-style string: words split on spaces, with single quotes, double quotes, and backslash
escapes. `FWTEST_ENGINE_BUILD_TIMEOUT` is the build limit in seconds. The default is 1200.

An interrupt is a child exit code of 128 or higher, including Ctrl+C. The run stops. The edit
record's drop restores the source. If `fwtest` itself is killed, the record stays and the next
`fwtest clean` (or the clean at the start of the next command) restores the file and runs the
marked rebuild. A failed clean rebuild leaves the mark.

Each engine case pays one release build of the mutated tree. A clean release build runs before
the next case whose file is not under `engine/`, and again at the end of the spec when the mark
is still set. Incremental builds reuse `engine/target`. Measured on 2026-10-02 in this checkout,
with that directory already warm: a mutated build took 4.4s to 7.5s, and a clean rebuild took
4.4s to 7.2s. A cold `engine/target` is slower than these times. The gate's audit tests call
`panic_probe`, `int_text`, and `int_chars`, which the default build exports.

## How a job is contained

- `fwtest` marks itself a child subreaper (`prctl(PR_SET_CHILD_SUBREAPER)`), so every descendant
  that detaches is re-parented to `fwtest` and stays findable.
- The command starts in a new process group with the limits applied before `exec`: nice 19,
  `ioprio_set` idle class, `sched_setaffinity` to the job's CPUs, and `PR_SET_PDEATHSIG` SIGTERM so
  the direct child hears if `fwtest` dies.
- With a systemd user session (`systemd-run --user` succeeds), the command runs inside
  `systemd-run --user --scope --collect -p CPUQuota=<half the cores>00% -p MemoryMax=<half of RAM>`.
  Stopping the scope stops everything in it. Without one, as on CI, the process group and the
  subreaper do the same work.
- To stop a job: SIGTERM every process in its tree (walked through `/proc/<pid>/task/*/children`),
  wait up to 3 seconds, SIGKILL whatever is left, wait up to 3 more seconds, and report any PID
  that survived.
- The picture tours and the rig need a display. `fwtest` passes the environment through unchanged
  apart from what the rig sets for itself; it never opens a window on the developer's display.

## What changes for the people who use it

- The developer runs `fwtest gate` where they ran `scripts/verify.py`, and keeps using the machine
  while it runs. While working, `fwtest gate --touched` runs only the touched areas; CI runs the
  rest.
- Agents run every suite through `fwtest`. `run-alone.sh`, `scripts/verify.py` and
  `scripts/mutate.py` are deleted once `fwtest` reaches parity (below), with every caller moved in
  the same change: README, `agents.md`, CI and the workflow notes.
- CI installs a Rust toolchain and runs `fwtest gate --backend-only`, the desktop suite through
  `fwtest run`, the mutation cases and `fwtest rig --server xvfb …` where it ran the Python scripts
  (see [CI](#ci)).

## Parity

`fwtest` replaces the Python scripts only when, on the same commit:

- `fwtest gate` and `scripts/verify.py` pass and fail on the same steps, checked on a commit that
  passes and on one with a deliberately failing test;
- `fwtest mutate scripts/mutations/look.json` and `scripts/mutate.py` report the same case names
  as caught, survived and not found;
- a rig run leaves no `kwin_wayland --virtual`, Xwayland or rig `dbus-daemon` behind, including when
  `fwtest` is sent SIGTERM mid-run and when it is sent SIGKILL and `fwtest clean` runs after it;
- the desktop's load average during a gate run stays under half the core count.

## Not in scope

Windows. The harness is Linux tooling; the Windows release workflow does not use it. Running
mutation cases in parallel, which needs a copy of the checkout per worker, comes later if the
sequential run proves too slow.
