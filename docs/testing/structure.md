# How FlexWeek's tests are laid out

The rules are in spec.md (Validation & Tooling, "Testing structure"). This page is how to follow them.

## Where a test goes
- Desktop tests live in one folder per area: `desktop/tests/<area>/test_<behaviour>.py`, each folder a package
  (an empty `__init__.py`). The areas are the names in `desktop/tests/pictures/screen.py`'s `AREAS`.
- A file is named after the behaviour it checks (`test_drag_a_block.py`), never after the pull request, audit,
  lane or finding that added it. Test functions say what the student sees or does.
- Logic that lives in the Rust engine is tested in the engine (`engine/engine/tests/<behaviour>.rs`, run by
  `cargo test`). Python keeps the tests of what the wrappers still decide (docs/engine/adapters.md).
- Backend tests stay in `backend/tests/`, named the same way.
- `desktop/tests/e2e/` is the small set that keeps the real local server and sign-in: accounts, sync, and save and
  undo round trips through the server.

## What a code test checks
Behaviour only: what a click, key, drag, save, undo or sync does, the state that results, the words a student
reads, accessible names and keyboard paths. Not colours, pixel positions, sizes or contrast. Those become screens
in `desktop/tests/pictures/screens_<area>.py`, each with the checks the reviewer makes (see `screen.py`).

## Looking at your screens locally
The renderer draws them offscreen, in the same fixed setup CI uses, so nothing opens on your display. Run it
through fwtest, which queues it behind other suites and caps it like any job:

```sh
fwtest pictures render --set touched             # the screens your branch touches, yours and origin/main's
fwtest pictures render --set full                # every screen in every variant: slow
```

It prints where the pictures went; for `touched` it also prints the `compare` and `page` commands that turn the
two sides into the review page (docs/tooling/fwtest.md, "Pictures"). To check that a new screens file loads and lists what you meant, without
drawing anything: `.venv/bin/python scripts/pictures/render.py --list`. A screen whose `prepare` raises shows on
the page with its error rather than a picture.

## The shared pieces (do not copy them)
- The clock: every test starts at Thursday 2026-11-05 19:00 (`backend/tests/fake_clock.py`). Move it with the
  `clock` fixture or `fake_clock.CLOCK`; never patch `now_ms` or `datetime`.
- A clean computer: the desktop conftest removes the look file and the week-start file and resets the 24-hour
  clock around every test.
- Waiting: `desktop/tests/waiting.py` (`wait_until`, `expect`). No `time.sleep`, no `QTest.qWait` with a fixed
  time; a test that needs a timer to fire moves the time it reads or waits on the signal.
- Windows: `desktop/tests/light_app.py` (`window`, `open_light`, `LightWindows`). A test makes its own state on top
  of the signed-up account; a module-wide window is only for read-only tests.
- Mutation specs (`scripts/mutations/*.json`) point at the test that catches each one; when a test moves or is
  rewritten, its specs move with it.
