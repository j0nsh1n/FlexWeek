# Contract: Stage 7 — month view for deadlines and projects

Status: proposed. Claude owns the browser/desktop frontend. Grok owns
persistence and the authenticated month API. Both clients continue to use the
same HTML, CSS and JavaScript frontend.

This contract is based on `grok/stage6-transfer-limit` at `f268b7e`.

GLM review was attempted through OpenCode, but the requests timed out without
returning review output. This file was written with the backend slice and then
checked against the combined implementation and verification evidence.

## Goal

A student can scan one calendar month for due dates and multi-day homework,
then open any visible date in Day view. Year view stays later optional work.
Student trials and UI clutter checks are frontend and release work, not this
API.

## Owner decisions (proposed defaults)

1. Month is a **read**. `GET /api/month?month=YYYY-MM` adds a compact calendar
   over existing weeks and assignments. No new table. Existing JSON on week,
   day, assignment and preference routes does not change.
2. `month` is a four-digit year, a hyphen and a two-digit month. The first day
   of that month must fall in 2000-01-01..2099-12-31. `2026-9`, `2026-09-01`
   and `2026-13` are 422.
3. The payload includes a **complete-week grid**: Monday of the 1st through
   Sunday of the last day, clipped to 2000-01-01..2099-12-31 so January 2000
   and December 2099 do not invent out-of-range dates. Leading and trailing
   days have `in_month: false`. Each day carries `week_start` from `monday_of`,
   including a Monday before 2000-01-01 when that is the week's Monday, so Day
   navigation uses the same label `GET /api/day` would.
   Calendar dates remain limited to 2000-01-01..2099-12-31. Week and assignment
   routes accept `1999-12-27` as the single lower-edge week start because it is
   the Monday containing 2000-01-01 and 2000-01-02. No other 1999 date is valid.
4. **Deadlines** are assignments whose due calendar date lands on the grid,
   open or completed, ordered by `due` then `id`. Completed items stay visible
   so finishing work does not erase the date.
5. **Overdue** is open homework whose due calendar date is before `grid_start`.
   It is a list, not pinned to day 1.
6. **Projects** are open assignments that belong on this month and are more
   than a single due-date pin: notes, links or a checklist, or placed sessions
   on two or more distinct grid dates. A one-session homework with no details
   is only a deadline.
7. A session **pins a date** only when it has a `start` and that day's index is
   in `days`. Unplaced candidate days do not paint the whole week. Locked
   non-session blocks with a start (school, sport, sleep) add `locked_count`
   and `scheduled_min` the same way Day `scheduled_min` counts them.
8. `preferred_view` stays `week` or `day`. Month is session navigation until
   the Stage 5 preference contract is approved. Year view is out of scope.
9. Date-to-Day navigation is frontend: the cell's `date` is `GET /api/day`'s
   query. This slice does not add a write that jumps the week.

## 1. Month calendar

`GET /api/month?month=YYYY-MM` is authenticated. 422 if `month` is missing or
malformed. 401 without a session.

```json
{
  "month": "2026-09",
  "start": "2026-09-01",
  "end": "2026-09-30",
  "grid_start": "2026-08-31",
  "grid_end": "2026-10-04",
  "days": [
    {
      "date": "2026-08-31",
      "week_start": "2026-08-31",
      "in_month": false,
      "due_ids": [],
      "session_count": 0,
      "locked_count": 0,
      "scheduled_min": 0
    }
  ],
  "deadlines": [
    {
      "id": "hw-essay",
      "title": "Essay",
      "due": "2026-09-16T23:59",
      "date": "2026-09-16",
      "completed": false,
      "estimate_min": 120,
      "unplanned_min": 120,
      "revision": 1
    }
  ],
  "projects": [],
  "overdue": []
}
```

Rules:

- `start` / `end` are the first and last calendar dates of `month`.
- `grid_start` / `grid_end` are the clipped week grid. `days` is every date in
  that closed range, in order.
- `due_ids` on a day are assignment ids whose due calendar date is that date,
  in the same order as `deadlines`.
- `session_count` is placed work sessions on that day (flexible with
  `assignment_id`, or locked pomodoro work chunks with `assignment_id`), the
  same membership as Day `sessions`, but only blocks that have `start`.
- `locked_count` is locked blocks on that day that are not those work chunks
  and that have `start`.
- `scheduled_min` is the total `duration_min` of those placed sessions and
  locked blocks.
- `unplanned_min` uses the existing formula against planned minutes from the
  Monday of `start` (the month's first day), so September 2026 uses
  `2026-08-31`.
- Project rows add `session_dates` (sorted unique grid dates with a placed
  session), `has_notes`, `has_links`, `checklist_total` and `checklist_done`.
  An assignment is a project when it is open, appears as a deadline, overdue
  item, or has a placed session on the grid, and either has notes, links or a
  checklist, or has two or more `session_dates`.
- An account with no saved weeks returns zero counts, empty lists, and the
  full grid of empty days.

No change to existing endpoint JSON.

## Ownership

- **Grok, backend:** `GET /api/month`, the grid / deadline / project / overdue
  rules above, and backend tests.
- **Claude, frontend:** Month view, previous/next month, Today, clicking a
  date to open Day view, and frontend tests.
- **GLM, helper:** not available in this harness.

## Tests both sides add

- Month API, `month=2026-09`: empty account returns a 35-day grid from
  2026-08-31 through 2026-10-04, first day `in_month` false, 2026-09-01
  `in_month` true with `week_start` 2026-08-31, empty deadlines/projects/
  overdue. School 08:00–14:30 Monday–Friday of 2026-09-14 sets
  `scheduled_min` 390 and `locked_count` 1 on 2026-09-14..18 only. An open
  assignment due 2026-09-16T23:59 with no start is a deadline on that date and
  not a project; the same assignment with notes is a project with empty
  `session_dates`. Placed sessions on Tuesday and Wednesday of that week make
  a project with those `session_dates` even without notes. An unplaced session
  whose `days` include Tuesday does not increment Tuesday's `session_count`.
  Open homework due 2026-08-15 is overdue, not a September deadline. Another
  account's month is empty. 422 on a missing or malformed month; 401 without a
  session. January 2000 clips `grid_start` to 2000-01-01; December 2099 clips
  `grid_end` to 2099-12-31.
- Frontend (Claude): Month shows due titles on their dates; a project lists
  its session days; clicking 2026-09-16 opens Day view for that date; empty
  months have no leftover week headings; Year is not shipped. Clicking
  2000-01-01 loads the `1999-12-27` containing week before opening Day.

## spec.md changes on approval

- Required Behavior: Month view of deadlines and projects; a date opens Day
  view.
- API: `GET /api/month`.
- Acceptance Criteria: Stage 7's month navigation path. Year remains later
  work. Student trials stay a separate checklist item.

## Out of scope

- Year UI.
- Year API, stored `preferred_view: month`, student trials, PR review.
- Changing Day, week, assignment or preference JSON.
- Hosted deployment, installers, iOS checks.

## Verification (backend)

- Empty September 2026 grid is 35 days, 2026-08-31..2026-10-04.
- School week occupancy is only Mon–Fri of the saved week.
- Deadline pins, notes-as-project, two placed dates-as-project, unplaced
  candidates do not pin, overdue is separate, account isolation, 422/401.
- Range clips at 2000-01 and 2099-12.
- `.venv/bin/python scripts/verify.py --web-only` from this worktree.
