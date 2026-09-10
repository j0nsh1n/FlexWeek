# Verification

Run the source checks from the repository root with the existing Python 3.14
environment and Node 24:

```bash
.venv/bin/python scripts/verify.py
```

The command runs JavaScript syntax, every `frontend/tests/*.test.mjs` file,
Ruff, mypy, all pytest cases, and working, staged and committed-range diff
whitespace checks. A failed command, timeout, missing desktop dependency, empty
test suite or skipped Python/Node test makes it fail. It installs nothing and does not build or
publish a binary. Qt cases use temporary profiles and databases with Chromium
sandboxing enabled.

For environments with only the web dependencies:

```bash
.venv/bin/python scripts/verify.py --web-only
```

This runs the frontend and backend checks and explicitly reports desktop as
unverified. `.github/workflows/verify.yml` runs this variant on pushes and pull
requests using Python 3.14 and Node 24. The workflow has read-only repository
permissions. Its hosted execution is unverified until the branch is pushed.

## Coverage map

| Behavior | Automated evidence | Useful next-feature cases |
| --- | --- | --- |
| Accounts, expiry, ownership, CSRF, revision conflicts and retries | `backend/tests/test_accounts.py`, `test_account_edges.py`, `test_week_api.py`; `frontend/tests/accounts.test.mjs` | Another account, expired session, stale response and failed save |
| Dated weeks and migration | `backend/tests/test_weeks.py`, `test_migration.py`, `test_week_api.py`; frontend account/calendar tests | Monday validation, year/DST boundaries, repeat migration, unsaved week navigation |
| Solver placement, priorities and explanations | `backend/tests/test_solver.py`, `test_completed.py`, `test_solver_invariants.py` | Contested capacity with unequal domains, completed work, deadline/earliest bounds, timeout partial results |
| Missed occurrences and recovery | Solver tests; WebEngine `phase6` case | One day of a series, cross-day movement, completed work, restore/save/reload |
| Grid gestures and event wiring | `frontend/tests/calendar-interactions.test.mjs`; WebEngine `calendar` case | Snap boundaries, cancel, a second pointer, move/resize, double-click, context menu and persisted reload |
| Imports, exports, drafts, categories and completion | `frontend/tests/phase5-slices.test.mjs`; `backend/tests/test_phase5.py` | Invalid input, repeat import, maximum merged size, unusual/maximum Unicode IDs, multi-day flexible tasks, completed placement round trip and exported draft reimport |
| Reminder preferences and session cleanup | Phase 5 frontend/backend tests | Lead window, solved flexible work, completed/missed filtering, account transition, browser notification closure and alert cleanup |
| Desktop navigation, downloads and layout | `desktop/tests/test_origin.py`, `test_server.py`, `test_webengine.py` | External popup/navigation, offline draft download, 1280px/390px overflow |

The generated solver cases use 20 fixed seeds and independent integer-minute
arithmetic. They check purity, candidate days, grid/deadline bounds, occupied
slots, completed work and explanations. They are not an exhaustive proof of
search optimality or a performance benchmark.

Node tests run the application in a simulated document. WebEngine tests load
the real HTML, CSS and JavaScript, dispatch DOM events, save through the real
API, and reload from SQLite. Synthetic pointer events test event wiring but do
not prove hardware pointer capture, touch scrolling or OS notification delivery.

## Adding coverage with a feature

1. Identify the behavior in the map and write a case with a concrete input and
   independently determined output. A fixture captured from current output
   cannot establish that the output is correct.
2. Cover the successful action and its relevant failure boundary. Examples
   include a cancelled gesture, rejected import, failed save, account change or
   exhausted scheduling window.
3. For event-driven UI behavior, extend a real WebEngine case alongside fast
   Node tests. The integration result can include a save and reload so the
   check covers persistence as well as the displayed draft.
4. Demonstrate the test failing for the intended defect before fixing it, or
   temporarily remove the behavior in an isolated copy. Inspect the assertion
   mismatch; a missing dependency or syntax exception proves nothing about the
   behavior.
5. Run the full command above. The test glob and pytest discovery pick up new
   tests automatically. Update this map when a new feature needs a new testing
   layer, and record remaining limitations with the handoff.

## Release checks outside the source gate

The full source gate is not a release certification. A packaged Linux build
needs the same create/save/reload and recovery paths exercised through the
packaged executable in a fresh profile. `DESKTOP.md` describes the build and
artifact checks. Windows execution, Safari/iPhone, physical touch, keyboard
accessibility, notification permission/sound and visual contrast remain separate
checks. The WebEngine probes cover close-to-tray in a source checkout, but the tray icon path
is only proven in the packaged build, because that bug never occurred in a source checkout.

No hosted security audit or production configuration check runs here. Existing
account tests prove their particular isolation/CSRF/revision cases, not the
safety of every deployment.

## Findings from the September 8–9 pass

The regression cases reproduced and now protect against:

- Cancelled pointer gestures creating or changing blocks.
- In-page and browser notifications surviving sign-out, solved flexible tasks
  receiving no reminders, and an identical reminder being suppressed in the next account.
- Legacy imports accepting invalid starts or scheduling bounds; day merges
  exceeding the 100-block limit; invalid day envelopes; valid IDs such as
  `__proto__` being rejected, and maximum-length/Unicode IDs drifting from the API.
- A file read crossing an account change and replacing the next account's week.
- A delayed preference response changing the next account's theme.
- Unimportable downloaded drafts.
- Completing a solved task discarding either its spent slot or its original
  candidate days. The persisted completed day now round-trips independently;
  WebEngine `completion` covers save/reload/solve.
- A day import duplicating a multi-day flexible assignment, and text/day export
  disagreeing with the placement visible after Solve.
- A second account login discarding the first account's suspended draft.
- Viewing another week silencing reminders for today's loaded week.
- Saving unchanged occurrence fields unnecessarily splitting a recurring block.
- Lower-priority reading beating exam preparation because its placement domain
  was smaller, followed by optional skip branches exhausting the solver budget
  on a feasible energy-sensitive week.

The source findings and platform limitations remaining after review are recorded
in `context.md`. Test totals come from the command output, not a fixed expected
count in this document. The solver timeout test uses a controlled clock to
confirm that budget expiry retains a partial placement and explains unplaced
work; the existing packed-week test checks real elapsed time.
