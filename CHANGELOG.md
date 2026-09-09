# Changelog

All notable changes to FlexWeek are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Repeatable full-source verification command, web CI workflow, a feature
  coverage guide, generated solver invariants and real calendar/completion
  WebEngine regression checks (2026-09-08).
- Multi-day locked blocks open with Edit this day vs Entire series: occurrence
  edits can remove one weekday or split a changed day into its own block; series
  edits still change every weekday together. Context menu mirrors those choices.
- Start reminders: preferences for enable, lead minutes and sound. While the tab
  is open, FlexWeek polls due starts (Daily Scheduler start-alert math), shows an
  in-app toast, and uses the Notification API when permitted. Desktop system-tray
  alerts are deferred (no new tray dependency in this slice).
- Category chips in the editor and a sidebar legend (School, Study, Homework,
  Sports, Activity, Meals, Sleep, Free) with stronger grid colors.
- Per-block completed flag with form checkbox and context toggle; survives
  save/reload.
- Export current week as JSON (Shift-click for plain text) and import a
  FlexWeek JSON week/day file into the matching week without touching other
  weeks. Context menu can export one day as JSON.
- Week grid drag interactions: empty drag creates a locked block on the 15-minute
  grid, click-empty creates a 60-minute block clipped to the next block, drag body
  moves, edge resize, click selects, double-click opens the editor, and a context
  menu offers Edit/Delete. Changes use the existing dirty/save path.
- Optional activity category with a thin color palette (School, Study, Homework,
  Sports, Activity, Meals, Free); older weeks without a category still load.

### Fixed
- Cancelled calendar gestures no longer save, and secondary pointers cannot
  finish another pointer's gesture (2026-09-08).
- Signing out clears private reminder alerts. Delayed preference responses and
  file reads cannot change the next account. Today's loaded reminders continue
  while browsing a different week (2026-09-08).
- Signing out also closes live browser notifications, solved flexible tasks can
  trigger reminders, and suspended drafts remain isolated by account (2026-09-09).
- Legacy and day imports validate starts and scheduling bounds before changing
  the week, including the resulting merged size and occurrence-ID collisions.
  Valid unusual IDs survive import, and downloaded drafts use the importable
  export format (2026-09-08).
- Saving an unchanged occurrence keeps its recurring series intact (2026-09-08).
- Completing through the menu or editor retains the task's solved placement
  as spent time without losing its candidate days. Day and text exports follow
  the visible solved placement, and ambiguous day imports cannot duplicate a
  multi-day flexible assignment (2026-09-09).
- Exam preparation wins contested capacity even when a lower-priority reading
  task has fewer possible placements. The solver first looks for a complete
  schedule before exploring optional omissions, avoiding a reproduced timeout
  on a feasible energy-sensitive week (2026-09-09).
- A task you finished but left listed on several possible days no longer blocks
  that hour on every one of them. It was one piece of work done once, and it
  could push three real tasks off the week. A finished task that was actually
  placed on a day still holds that time, because you really did use it.
- When finished work is what fills a slot, FlexWeek says so instead of telling
  you the time is taken by school, sports or sleep.
- A task you have ticked off no longer competes for a slot. Finished work used
  to be scheduled again, so a completed essay could take the last free hour and
  FlexWeek would tell you your real homework did not fit because a
  higher-priority task took the slot. A finished task that already had a time
  keeps it; one that never had a time is simply left alone.
- A damaged or unrecognised export file is refused with a reason, and the week
  on screen is left exactly as it was. Previously the file was written into your
  week and drawn on the grid before the save failed, so a bad file could wipe
  what was there. Files from a newer version of FlexWeek are refused too.
- Dragging a single day of a repeating block no longer silently retimes every
  other day of it. The drag is refused and FlexWeek points you at Edit
  occurrence or Edit series, which is how every other change to a repeating
  block already works. One-off blocks still drag and resize normally.
- Importing a week now stops without changing the open week when the target
  week cannot be loaded. Day-file imports preserve the other occurrences of a
  repeating block, including when the same file is imported again.
- Desktop new-window links no longer leave hidden browser pages running; only
  HTTP(S) external links are sent to the system browser (2026-09-07).
- Desktop users can save an unsaved draft through a native file dialog.

### Added
- Scheduling explanations now use student-facing messages, can highlight the
  affected task, and show ok/tight/danger deadline slack on placed tasks.
- A solved week can recover from one missed weekday occurrence of a locked
  block. FlexWeek keeps the missed occurrence in the saved week, re-solves the
  remaining tasks, lists time and day changes, and lets the user restore it.
- Dated weeks. Your schedule is now kept per calendar week instead of as one
  rolling week, with Previous, Next and Today controls, the date shown on each
  day header, and a picker listing the weeks you have saved. Each week keeps
  its own unsaved edits, so moving between weeks never loses work and never
  copies one week's blocks into another.
- `GET /api/weeks` lists the weeks an account has saved, so a week you did not
  know about is still reachable.
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
- Existing accounts are migrated on first start: the one saved week becomes the
  week containing that day, keeping its blocks and its revision.
- An unsaved-draft download is now named for its week and carries the week in
  its JSON, so drafts from two weeks are no longer indistinguishable files.
- "New week" and the legacy-import confirmation now name the week on screen
  instead of saying "your current week".
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
