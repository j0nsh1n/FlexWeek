# FlexWeek architecture

| Layer | Role |
|---|---|
| Desktop interface | Material 3 in Qt Quick/QML, with Python bridges for account screens, the week editor, settings, sheets and save/retry state |
| Desktop session | `NativeSession`: edits, planning calls, focus, reminders, alarms, undo and preferences |
| FastAPI | Session and ownership checks, bounded validated requests, account APIs and the solver route |
| Rust engine and store | Planning, calendar rules, Qt-free desktop logic, validated storage and SQLite migrations |
| SQLite | Users, hashed sessions, account-owned weeks and revisions, preferences, routines, restore points and sync records |

The interface does not implement placement. A solver result is a preview until the
student accepts it or the app plans homework. Editor saves persist the student's
entered blocks. The original Sep 6 contest brief (working title Reslot) is in git
history (`docs/cac-build-plan.md`, removed 2026-11-06).

## Data flow

```text
QML control → Material bridge → NativeSession → NativeClient → FastAPI → Rust store
                                      |                              |
                                      └──────── Rust engine ←────────┘

Register/login → expiring HttpOnly cookie → authenticated account
                                             |
Editor → revision-checked change → account-owned SQLite row
          | 409 conflict                      |
          └→ retain draft + reload       GET /api/week → editor

Entered blocks → POST /api/solve → SolveTrace → grid + results
Preference change → PUT /api/preferences → account preference
```

Every private query derives its owner from the session. The desktop sends an
expected account ID so a request made before an account change is rejected.
Writes carry a custom header and same-origin checks; no CORS is enabled.
Password hashes use scrypt; SQLite stores hashes of random session tokens, not
the cookie values.

Week writes use transactions and optimistic revisions. A repeated identical
payload is a no-op; stale differing writes return 409. Failures preserve the
desktop's unsaved in-memory draft. Session loss hides account content; only the
same account can restore that draft. Explicit sign-out clears it.

Legacy localStorage is available solely for an explicit validated import.
Demo JSON remains test-only; no product endpoint exposes sample weeks.

## Time model

Stored weeks are keyed by Monday. The computer can show a week starting on any
day, which the API reads and writes across the one or two stored Monday-keyed
weeks it covers. Days use local `HH:MM` strings and naive local ISO deadlines.
The planner uses 15-minute slots over the whole day; a block may start and end
at any minute and takes every slot it touches. Overlap uses half-open ranges
`[start, end)`. See `spec.md` and `docs/engine/contract.md`.

## Desktop client

The desktop is one Python application. Material 3 is its only student interface,
written in Qt Quick/QML. `desktop/native/material/host.py` defines
`MaterialPage`, a `QQuickView` owned by the QObject controller `NativeWindow`
in `desktop/native/window.py`. The controller owns the session, sync, reminders,
alarms, tray, updates, local look file and drawing-error page. QML provides
sign-in, recovery, setup, Day, Week, Month, My day, Settings, Focus and the
app's sheets. `QQuickView` paces frames to the screen rather than using the old
Widgets host's 60 Hz clock.

The QML shell calls `MaterialBridge` and its screen bridges. Those bridges call
`NativeSession`; QML does not make HTTP requests, open SQLite or call the engine
directly. `NativeSession`'s client asks the Rust service in the same process, on
worker threads, with no server and no network port.
Windows and Linux are the download targets. There is no browser client,
`QWebEngineView`, JavaScript bridge or npm build. See DESKTOP.md.

If Qt Quick cannot draw with the graphics card, the shell saves unsaved edits
and starts one new copy with `QT_QUICK_BACKEND=software`. A newer app version
tries the graphics card again. If software drawing fails too, the shell shows a
plain error page with Quit and Try again.

The Android app uses the same Rust engine and store. Release and debug builds
include Today, Week, Add homework, Plan and Running late.
