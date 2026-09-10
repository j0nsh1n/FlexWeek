# FlexWeek architecture

| Layer | Role |
|---|---|
| Browser | Account screens, week editor, theme, save/retry state and solver result display |
| FastAPI | Session/ownership checks, bounded validated requests, account APIs and static files |
| SQLite | Users, hashed sessions, account-owned weeks/revisions, preferences and auth counters |
| Python solver | Pure synchronous constraint placement on the existing 15-minute grid |

The browser sends weeks to the Python solver; it does not implement placement.
A solver result is a preview. Editor saves persist the student's entered blocks.
The original Sep 6 contest brief (working title Reslot) is archived in
[docs/cac-build-plan.md](docs/cac-build-plan.md).

## Data flow

```text
Register/login → expiring HttpOnly cookie → authenticated account
                                             |
Editor → PUT /api/week + revision → account-owned SQLite row
          | 409 conflict                      |
          └→ retain draft + reload       GET /api/week → editor

Entered blocks → POST /api/solve → SolveTrace → grid + results
Theme setting → PUT /api/preferences → account preference
```

Every private query derives its owner from the session. The browser sends an
expected account ID to detect cookie changes in another tab. Writes carry a
custom header and same-origin checks; no CORS is enabled. Password hashes use
scrypt; SQLite stores hashes of random session tokens, not the cookie values.

Week writes use transactions and optimistic revisions. A repeated identical
payload is a no-op; stale differing writes return 409. Failures preserve the
browser's unsaved in-memory draft. Session loss hides account content; only the
same account can restore that draft. Explicit sign-out clears it.

Legacy localStorage is available solely for an explicit validated import.
Demo JSON remains test-only; no product endpoint exposes sample weeks.

## Time model

Monday–Sunday day indices, local HH:MM strings, 06:00–23:00, 15-minute slots:
68 per day and 476 per week. Overlap uses half-open ranges `[start, end)`.
Weeks are keyed by the Monday of that week. See `spec.md`.

## Desktop client

The desktop application is a PySide6 QWebEngineView window that runs the FastAPI
backend in-process on a loopback port, or loads a hosted origin when
`FLEXWEEK_DESKTOP_ORIGIN` is set. Windows and Linux are the download targets.
There is no native JavaScript bridge. See DESKTOP.md.
