# Native Python migration

Jonathan selected a native Python desktop application on 2026-09-17, retiring
browser delivery. The baseline is `a92feef`, including the local appearance work
after 0.11. This document tracks implementation, not a claim of feature parity.

## Destination and implementation choice

Python 3.14 and the already pinned PySide6 6.11.2 provide Qt widgets. Native
launch imports no Qt WebEngine and executes no JavaScript. The existing Python
backend runs on a private loopback port, with browser files disabled. Keeping
that boundary preserves account ownership, revisions, operation retries and
transactions while the interface changes. A direct service extraction was
considered but would also rewrite the account and transaction boundary inside
`backend/app.py`. It is not required to remove the browser interface.

`QNetworkAccessManager` owns asynchronous requests and an in-memory cookie jar.
The controller owns account lifetime, the selected dated week, drafts and the
current solver result. Widgets show that state and emit user actions. Each
account reset retires its manager and cookies, and invalidates outstanding
callbacks. A failed save retains its payload and operation ID for retry.

The database stays at `QStandardPaths.AppDataLocation/flexweek.db` under the
application name `FlexWeek`. Existing accounts need a fresh login in the native
client. Chromium cookies are not copied. An explicit `--database` path supports
isolated source verification. No existing database is moved or replaced.

## Migration units and verification gates

1. Native foundation. Account registration, recovery-code acknowledgment,
   login/logout, dated week loading, fixed commitments, homework creation,
   solve explanations, atomic saving and restart persistence. Verify real Qt
   widgets against a temporary database, two-account isolation, stale replies,
   revision conflicts, retained drafts and absence of WebEngine imports.
2. Calendar and homework parity. Day and Month summaries, drag create/move/resize,
   occurrence versus series scope, category shortcuts, exact deadlines,
   completion, notes/links/checklists and keyboard equivalents. Translate the
   existing calendar, Day, Month and assignment tests into native interaction tests.
3. Planning and reuse parity. Undo/redo, clipboard and conflict previews,
   routines, unfinished work, missed sessions, running late, project spreading
   and availability. Verify transaction retries, maximum planned minutes,
   identity across weeks and recovery after every rejected write.
4. Focus and preferences parity. Focus/break timers, once-only progress credit,
   explicit completion, reminders, alarms/snooze, Spotify, theme packs, look
   controls and tray behavior. Verify wall-clock timing, sign-out cleanup,
   preference round trips and native notification limits.
5. Account recovery and files. Forgotten-password recovery, password/code
   replacement, deletion, week/day files, restore points and previewed account
   transfer. Verify wrong-password session preservation, stale previews,
   replacement confirmation, import limits and restart recovery.
6. Retirement and delivery. Switch the normal launcher after parity, remove
   browser/Chromium runtime and hosted-client configuration, move shared assets,
   and replace browser-based release probes with native smoke checks. Preserve
   backend solver/security tests. Packaging validation and platform execution
   are separate from source tests. Executables remain unbuilt in this work.

## Current parity status

1. Native foundation: verified 2026-09-17. `python -m desktop.native` starts Qt
   widgets against the existing Python API with browser files disabled. Real
   widget tests cover registration and recovery-code acknowledgment, login and
   logout, dated weeks, a saved fixed time after restart, homework plus Solve,
   two-account isolation, stale replies, a 409 that keeps the draft, and no
   WebEngine import. `python -m desktop.main` is now the native launcher.
2. Calendar and homework parity: verified 2026-09-17. Day and Month talk to
   `GET /api/day` and `GET /api/month`. Drag create/move/resize uses the same
   15-minute grid as the web calendar; a repeating locked block refuses a
   one-day drag. Occurrence edits split a one-day block. Homework keeps exact
   due times, notes, links, a checklist and a completion stamp, and a notes-only
   edit keeps the existing session. Keyboard W/D/M switches Week/Day/Month;
   Delete removes the selected occurrence or block. Type chips open Add already
   armed.
3. Planning and reuse parity: verified 2026-09-17. Undo and Redo walk the last
   saved change on the week on screen. Copy, paste, duplicate and copy-day use
   an internal clipboard (Ctrl/C/V/D never touch the OS clipboard). A collision
   preview leaves overlapping times unchecked and never force-pastes. Homework
   paste keeps the assignment id and shares remaining unplanned minutes across
   a batch. A 100th block is refused. Routines store locked times only and apply
   through the same preview, writing `snapshot_label` on `/api/changes`.
   Unfinished homework from an earlier saved week plans here with the same id.
   Missed days recover through `/api/solve` recover. Running late previews a
   solve then saves one locked "Running late" block. Spread posts
   `/api/assignments/{id}/spread` then confirms through `/api/changes`.
   Availability is GET/PUT `/api/preferences` protected/study_windows/day_cutoff.
4. Focus and preferences parity: verified 2026-09-17. Work/break/long-break
   timers use wall-clock `endsAt`, persist per account in the session store, and
   clear on sign-out. Completing a work phase credits `focus_minutes` once and
   does not push Undo. Quick focus credits nothing. Homework sessions end with
   Finished / more time / break. Reminders fire once per block start inside the
   lead window. Alarms snooze five minutes. Spotify opens only `open.spotify.com`
   share links. Theme packs PUT `theme_pack` with the axis `theme` field. Look
   knobs stay device-only JSON. The tray can hide the window while reminders
   keep running. Native notification delivery is still the OS tray message;
   offscreen tests do not prove a real desktop notification.
5. Account recovery and files: verified 2026-09-17. Forgot-password recovery
   uses `POST /api/auth/recover`. A wrong login or current-password 401 leaves
   the signed-in session in place. Password and recovery-code replacement, account
   deletion, restore-point create/preview/restore, week and day JSON files, and
   previewed account transfer talk to the existing Stage 3/6 API. A stale restore
   token is refused and the week on screen is unchanged.
6. Retirement and delivery: verified 2026-09-17. `python -m desktop.main` and
   `python -m desktop.native` launch native widgets. The private server starts
   with browser files disabled. `--smoke-test` registers a throwaway account,
   saves a week, and writes a report without Chromium. `desktop/webengine.py`
   remains only for leftover probe tests. Packaging scripts and installers are
   unchanged and still unbuilt.

## Sources

The feature inventory comes from `frontend/`'s 18 JavaScript modules,
`desktop/main.py`, `backend/app.py` and `docs/verification.md` at the baseline.
Qt documents asynchronous network and cookie ownership in
[QNetworkAccessManager](https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QNetworkAccessManager.html).
The widget APIs are listed in
[Qt Widgets](https://doc.qt.io/qtforpython-6/overviews/qtwidgets-widget-classes.html).
