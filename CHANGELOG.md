# Changelog

All notable changes to FlexWeek are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- Desktop new-window links no longer leave hidden browser pages running; only
  HTTP(S) external links are sent to the system browser (2026-09-07).
- Desktop users can save an unsaved draft through a native file dialog.

### Added
- Windows standalone build script and isolated real-WebEngine account, link and
  offline-draft tests (2026-09-07); Windows execution remains unverified.
- Linux desktop app: a PySide6 web-engine window with the FlexWeek backend
  bundled in, so it runs with no separate server and no Python installed. It
  starts its own backend on a loopback port and keeps its database in your user
  data directory. A persistent profile means a sign-in survives restarting the
  app; there is a retry screen if the backend cannot be reached, and external
  links open in the system browser. Build with `desktop/build_linux.sh`.
  Point it at a hosted deployment with `FLEXWEEK_DESKTOP_ORIGIN`.
- Desktop packaging recommendation: PySide6 web-engine shell around the hosted
  app (`DESKTOP.md`).
- 2026-09-07: Username/password accounts, expiring sessions, account-owned SQLite
  weeks and saved Nocturne/Slate themes adapted from Daily Scheduler.
- Save retry, revision-conflict handling, unsaved draft download and explicit
  import of legacy browser weeks; same-account draft restoration after expiry.
- Basic request protection, authentication throttling and bounded input.
- Account/API and frontend state tests.
- Add / edit / delete forms for locked blocks and flexible tasks.
- Last week saved in the browser; a corrupt save resets to a demo.
- Constraint solver: backtracking with MRV and forward checking, 150 ms cap.
- Solve button and a debug panel (`solve_ms`, placed count, unplaced titles).
- Placed flexible tasks painted on the week grid.
- App logo and favicon, cropped from `FlexWeek.png` (lime phone + dumbbell).
- Partner-style demo weeks: Alex and Jordan each have 4 locked blocks and 8
  flexible tasks.
- 15-minute tick marks on the week grid, duration labels on locked blocks, and
  due/course pills on flexible tasks.

### Changed
- Linux builds preserve previous artifacts and use separate staging directories.
- 2026-09-06: Revise the post-Phase-3 roadmap for accounts, app/web delivery,
  Daily Scheduler interactions and themes, with design and audits deferred.
- Week grid colors follow the logo (paper gray, lime, dark teal) instead of a
  generic dark dashboard.
- Slot starts are the half-open range `[06:00, 23:00)`; `23:00` is not a legal
  start.

### Removed
- `grok-desktop-prompt.md` after the desktop packaging recommendation landed.
- Product demo picker/endpoints and anonymous localStorage saving. Seed schedules
  remain test fixtures.
- `backend/tests/test_models.py`, which still imported the pre-Pydantic
  dataclass API and broke collection.

## [0.1.0] — 2026-09-06

### Added
- Pydantic `TimeBlock`, `Move`, `SolveTrace` in `backend/models.py`.
- 15-minute slot helpers in `backend/slots.py`.
- FastAPI app serving `frontend/` plus `GET /api/demos/{name}` and a stub
  `POST /api/solve`.
- Week grid UI with a demo switcher.
- `PHASES.md` contest calendar.
