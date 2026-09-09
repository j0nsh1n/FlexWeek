# context.md — FlexWeek

## Current State
- Date: 2026-09-09. Branch `test/deeper-verification`, based on
  `feat/phase5-calendar-interactions` at `147687c`.
- Phase 5 calendar interactions and Phase 6 scheduling recovery are implemented.
  Accounts, Monday-keyed weeks, 15-minute placement and per-day `missed_days`
  recovery remain the product model.
- The deeper verification pass reproduced and fixed cancelled gesture writes,
  private reminder state surviving sign-out, stale account responses/file reads,
  invalid legacy/day imports, merged-week overflow, occurrence-ID collisions,
  unusable draft downloads, multi-day task duplication, per-account draft loss,
  completion losing candidate days, reminder leaks/gaps and priority inversion.
- Today's loaded week and solved flexible placements produce reminders while
  another week is selected. Sign-out closes both in-page and browser alerts.
- Source verification now has one runner, `scripts/verify.py`, a feature coverage
  map in `docs/verification.md`, and a web-only GitHub Actions workflow. The
  workflow has not run remotely; nothing has been pushed.
- Baseline was 121 Python and 40 frontend tests. The final full source gate ran
  153 Python and 61 frontend tests with no skips.
- Completed flexible work keeps its original candidate `days`; `completed_day`
  records the one occurrence whose `start` is spent. Both UI completion actions
  preserve and can restore the candidate set.
  Completed tasks without a placement stay outside scheduling; locked blocks
  retain their existing occupancy semantics.
- The previous Linux artifact was rebuilt by Claude on September 8. It predates
  this verification branch's fixes and has not been rebuilt in this pass.
  Packaged behavior, Windows execution, Safari/iPhone and physical touch remain
  unverified here. Desktop tray reminders are deferred.
- Default desktop mode uses a local database. Hosted mode uses the configured
  server; there is no automatic synchronization between them.

## Repo Landmarks
```
DESKTOP.md               PySide6 QWebEngineView recommendation + build status
desktop/origin.py        origin resolution, no Qt imports (unit-tested)
desktop/server.py        bundled uvicorn on a loopback port, no Qt imports
desktop/main.py          Qt window, persistent profile, retry panel
desktop/build_linux.sh   staged Linux build, previous artifacts preserved
desktop/build_windows.ps1 Windows standalone build preparation
desktop/tests/           origin/server tests and isolated real WebEngine probes
backend/weeks.py         week-date helpers, no framework import
backend/app.py           account/session/ownership APIs and static frontend
backend/storage.py       SQLite, scrypt, hashed sessions
frontend/app.js          account lifecycle, editor, server saves
```

## Domain Model
SQLite: users → sessions, many dated weeks keyed (user_id, week_start), one
preference row. Default desktop
mode uses a local per-user database; hosted mode uses the configured deployment.
There is no automatic synchronization between those databases.

## Non-Obvious Decisions
- A week's identity is its Monday. Blocks store a day index and derive their
  date, which is why the day-index solver needed no adapter at all.
- `weeks.py` pins the ISO shape with a regex before parsing, because
  `date.fromisoformat` also accepts "20260907" and "2026-W37-1".
- The migration is guarded on the weeks table existing, since PRAGMA
  table_info returns nothing for a missing table and ALTER TABLE would raise on
  a fresh database. It runs in an explicit BEGIN IMMEDIATE, not in
  executescript, which issues an implicit COMMIT.
- Registration no longer seeds a weeks row; the NOT NULL key would reject it,
  and a missing row already means an empty week.
- GET /api/week 422s a non-Monday rather than snapping it, so a client and
  server cannot disagree about which week is open while both think they won.
- The identical-blocks short-circuit deliberately runs before the revision
  check, preserving what the pre-dated code and tests already did.
- The desktop app bundles the backend and runs it in-process (owner asked for
  this 2026-09-07). It supersedes DESKTOP.md section 1, which said not to; that
  section's reasoning was about a *second process*, which this is not.
- The loopback port is chosen by binding a socket before create_app is called,
  because the backend pins its CSRF origin check and TrustedHostMiddleware to
  one exact origin. uvicorn is handed the already-bound socket.
- uvicorn runs with loop="asyncio" and http="h11" so the build does not depend
  on uvloop/httptools surviving being frozen.
- An invalid FLEXWEEK_*_ORIGIN is an error, not a silent fall back to local:
  a typo must not quietly open a different, empty database.
- The Qt profile is parented to the QApplication, not the window: parenting it to
  the window makes Qt warn "Release of profile requested but WebEnginePage still
  not deleted" and can crash on close.
- `profile_root()` reads QStandardPaths AppDataLocation, which derives from the
  application name, so main() sets that before building the profile.
- Nuitka is called directly instead of via pyside6-deploy, which rewrites its own
  spec with absolute machine paths on every run.
- Qt translations are included; stripping them made WebEngine warn about a
  missing en-US.pak at every start.
- PySide6 6.10+ documents Python 3.14. pywebview classifiers stop at 3.13.
- Qt WebEngine cannot be statically linked; onedir Chromium libs are expected.
- No Qt WebChannel / pywebview js_api in v1 (cookies and CSRF stay on the page).
- License file is GPL-3.0. Qt for Python is LGPLv3/GPLv2/commercial.

## Session Handoff
- 2026-09-09, `test/deeper-verification`: full local verification passed with
  153 Python and 61 frontend tests, Ruff, mypy, JavaScript syntax, and all diff
  checks. GLM and two Codex reviewers found the solver, completion, import,
  draft, reminder and export regressions now covered by focused tests. Gemini
  timed out twice through Antigravity and was not counted as review evidence.
- The two-stage solver finds ordinary complete schedules before considering
  optional task skips. This preserves the priority result for infeasible weeks
  and completes the reproduced energy-sensitive ten-task week within budget.
- The untracked `Github Templates/` and `reslot-cac-build-plan.md` remain
  untouched. `spec.md` is unchanged; its individual validation commands still
  apply. It does not yet document the persisted `completed_day` field; that
  contract update needs a separate approved spec edit.
- The CI workflow is unrun until pushed. The existing Linux package predates
  these changes; Windows, Safari/iPhone, physical touch, packaged behavior and
  OS notification delivery still need release-platform checks.
