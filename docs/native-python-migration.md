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
   WebEngine import. The WebEngine app remains the default launcher.
2. Calendar and homework parity: unverified.
3. Planning and reuse parity: unverified.
4. Focus and preferences parity: unverified.
5. Account recovery and files: unverified.
6. Retirement and delivery: unverified.

## Sources

The feature inventory comes from `frontend/`'s 18 JavaScript modules,
`desktop/main.py`, `backend/app.py` and `docs/verification.md` at the baseline.
Qt documents asynchronous network and cookie ownership in
[QNetworkAccessManager](https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QNetworkAccessManager.html).
The widget APIs are listed in
[Qt Widgets](https://doc.qt.io/qtforpython-6/overviews/qtwidgets-widget-classes.html).
