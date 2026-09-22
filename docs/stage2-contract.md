# Contract: Stage 2 — today's work easy to find and add

Status: approved by the owner for roadmap Stage 2 of the student experience
revision. The approval predates this line, which said "proposed" until it was
corrected on 2026-09-15; spec.md now carries Day view and `GET /api/day`.

Grok builds the backend parts and Claude builds the frontend parts against this
file at the same time. Neither side changes it alone.

Line references are to `feat/stage1-student-experience` at `130ee99`.

## Owner decisions (proposed defaults)

These are recommendations. The owner confirms them before implementation.

1. The header button is **Plan my homework**. After this week already has a
   solve trace, the same button reads **Update my plan**.
2. At `max-width: 800px` (the existing layout breakpoint,
   `frontend/styles.css:607-611`) the default view is the **day agenda**. Week
   view stays one control away. At 1280px the default is Week, with Day
   available.
3. **Due soon** is relative to the agenda date `D`. It is open homework whose
   `due` calendar date is `D` or `D + 1 day`, plus open homework whose `due`
   is before `D` at 00:00.
4. Available minutes use the existing grid end **23:00**
   (`backend/slots.py:7`). Stage 2 does not add a cutoff preference.
5. Recorded focus for a day is the total `duration_min` of **completed
   sessions on that day**. Lifetime `focus_minutes` stays on the assignment.
6. Keep the context menu as a secondary path. Agenda rows have Edit, Finished
   and Start focus in the open.

## 1. Day agenda and phone layout

### Today

- The planner is a seven-day grid plus a sidebar
  (`frontend/index.html:87-168`). `Today` in the week bar jumps to this week's
  Monday (`frontend/app.js:2691`), not to a day page.
- At `max-width: 800px` the layout stacks to one column
  (`frontend/styles.css:607-611`). The week grid still paints all seven days.
- The sidebar always includes Add, Tasks to place, Continuing, Focus and
  What Solve did (`frontend/index.html:109-167`). Empty lists still show a
  heading. Tasks to place and Continuing can name the same homework.
- Edit, complete and focus for a block live on the context menu
  (`frontend/index.html:177-186`) or after opening the editor.

### New

- A **view** is `day` or `week`. It is client state for the signed-in session.
  It is not stored on the server.
- **Day view** shows one calendar date. Previous and Next move by one day.
  Today opens the server's local today. The week of that date is still loaded
  through the existing week endpoints.
- Day view lists, in this order, and **omits a heading when that list is
  empty**:
  1. **Due soon** (decision 3).
  2. **Today's sessions**: work sessions whose `days` include that day's
     index, with start if placed.
  3. **Today's fixed time**: locked blocks on that day.
  4. **Next**: one line, always one of start, plan or add. If a placed
     unfinished session exists on that date, it is the earliest start. Else if
     due-soon homework has `unplanned_min > 0`, it is the first such
     assignment in due-soon order (`due`, then `id`). Else it is **Add
     homework**, including a day whose sessions are all finished.
- An empty day (no due-soon, no session, no locked block) shows one sentence
  and Add homework. It does not show empty section titles.
- Each session and due-soon row has **Edit**, **Finished** and **Start focus**
  in the row. Finished on a session uses the Stage 1 assignment Finished path
  (later sessions stay stored and unplaced). Start focus uses the existing
  timer.
- At 800px and below, Day is the first view after sign-in. A control switches
  to Week. At 1280px, Week is first. Both widths keep Add homework on screen
  without opening More or a context menu.

## 2. Quick entry and Plan my homework

### Today

- Add without dragging opens the full editor: type chips, title, Fixed vs
  Flexible, due date and time, duration, days, More options
  (`frontend/index.html:190-228`).
- The header button is **Solve** (`frontend/index.html:42`). Notes and the
  results heading still say Solve (`frontend/index.html:126`,
  `frontend/index.html:160`, `frontend/app.js:1054`).
- Setup's last step still says Add to my week and Solve
  (`frontend/setup.js:88`).

### New

- **Add homework** asks for title, due date, due time and estimated time.
  Saving it creates the assignment through `PUT /api/assignments/{id}` and a
  session this week through the existing week save, as Stage 1 already does.
- **Choose a time myself** opens the current editor (fixed vs flexible, days,
  start, More options). School and practice chips still open that editor.
- The header button, flex note, results heading and setup last step use Plan
  my homework / Update my plan (decision 1). The HTTP path stays
  `POST /api/solve`.
- Continuing's **Plan the rest here** stays. After it runs, the status tells
  the student to press Plan my homework (or Update my plan).

## 3. Lists, explanations and navigation

### Today

- `renderDebug` lists every explanation, including energy mismatch
  (`frontend/app.js:1750-1758`). Slack ok has no badge; tight and danger do
  (`frontend/app.js:27`, `frontend/app.js:1540-1545`). Slack copy is hour
  counts from `slack_sentence` (`backend/explain.py`).
- Week nav includes Export week and Import file
  (`frontend/index.html:95-97`). Theme is in the header and in Settings
  (`frontend/index.html:39`).

### New

- Results show unplaced work and the next action first. Successful placement
  (including energy mismatch and slack ok) is one collapsed line per week:
  "n tasks fit." Tight and danger stay visible as "due Tuesday" or "2 days
  left", not as a minute count. The full sentence remains on the row title.
- Day view does not repeat the same assignment in Tasks to place and
  Continuing. Continuing stays on Week view.
- Export week and Import file move into Settings. They leave the week bar.
  The header Theme select stays. Settings still contains the full preference
  form, including theme.

## 4. Daily workload

### Today

- There is no per-day scheduled / focus / free summary. Category colors exist
  on chips and blocks. Assignment `focus_minutes` is lifetime, not per day
  (Stage 1).

### New

`GET /api/day?date=YYYY-MM-DD` is additive. `date` is a naive local calendar
date in 2000-01-01..2099-12-31, not necessarily a Monday. 422 if missing or
malformed. 401 without a session.

The server loads that date's week (`monday_of(date)`), the account's
assignments, and returns:

```json
{
  "date": "2026-09-15",
  "week_start": "2026-09-14",
  "due_soon": [
    {
      "id": "hw-essay",
      "title": "Essay",
      "due": "2026-09-16T23:59",
      "estimate_min": 120,
      "focus_minutes": 0,
      "planned_min": 60,
      "unplanned_min": 60,
      "completed": false,
      "revision": 1
    }
  ],
  "sessions": [],
  "locked": [],
  "next_action": {"kind": "add"},
  "workload": {
    "scheduled_min": 0,
    "focus_min": 0,
    "available_min": 1020,
    "by_category": []
  }
}
```

Rules:

- `due_soon` is open assignments matching decision 3, ordered by `due` then
  `id`. Each carries `planned_min` and `unplanned_min` for `week_start`, same
  formula as `GET /api/assignments`.
- `sessions` are this account's work sessions (flexible with
  `assignment_id`, or locked pomodoro work chunks with `assignment_id`) whose
  `days` include that day index. Copies are rewritten from the assignment, as
  on `GET /api/week`.
- `locked` are locked blocks on that day that are not those work chunks.
- `next_action` is `{ "kind": "start", "block_id": "..." }`,
  `{ "kind": "plan", "assignment_id": "..." }`, or `{ "kind": "add" }`, using
  the Day view rule above.
- `scheduled_min` is the total `duration_min` of sessions and locked blocks
  that have a `start` on that day, including completed sessions that hold a
  slot. An open session with no `start` is listed in `sessions` on each of
  its candidate days but is not planned there (changed 2026-09-21, 0.14.1
  trust audit).
- `focus_min` is the total `duration_min` of completed sessions on that day
  (decision 5).
- `available_min` is unoccupied 15-minute slots from 06:00 up to 23:00 on
  that day (`backend/slots.py:6-8`). A stored block's start and
  `duration_min` already land on that grid. Occupied slots are locked blocks
  and completed sessions that hold a start. Open unplaced sessions do not
  occupy. Sleep that is stored as a locked block occupies like any other lock.
- `by_category` groups `scheduled_min` and `focus_min` by block `category`
  (`null` is its own group). Groups with both zeros are omitted. Order is
  scheduled_min descending, then category name.
- An account with no saved week for that Monday returns empty lists, next
  action `add`, scheduled and focus 0, available 1020 (17 hours).

No new table. No change to existing endpoint JSON.

## Ownership

- **Grok, backend:** `GET /api/day`, the due-soon / next-action / workload
  rules above, and backend tests. Existing assignment, week, changes and
  solve endpoints stay as Stage 1 left them.
- **Claude, frontend:** Day and Week views, the 800px default, Add homework
  quick entry, Plan my homework / Update my plan copy, collapsed results,
  slack in days, Export/Import in Settings, visible row actions, frontend
  tests and a WebEngine probe at 390px and 1280px.
- **GLM, helper:** fixture days (empty, school-plus-homework, overdue) and
  first-pass review of both sides. Whoever asks GLM checks its output.

## Tests both sides add

- Day API, date 2026-09-15 (Tuesday), week starting 2026-09-14: empty week
  returns next_action `{"kind": "add"}`, available_min 1020. School
  08:00–14:30 and a 60-minute completed session at 16:00 return
  scheduled_min 450, focus_min 60, available_min 570, next_action
  `{"kind": "add"}`. An open assignment due 2026-09-16T23:59 with no session
  is in due_soon and next_action is `{"kind": "plan", "assignment_id": ...}`;
  one due 2026-09-18T12:00 is not in due_soon. A placed unfinished session at
  16:00 makes next_action `{"kind": "start", "block_id": ...}`. 422 on a
  non-date; 401 without a session; another account's week is not visible.
- Frontend: at 390px the first signed-in view is the day agenda and Add
  homework is on screen; at 1280px Week still shows seven days; an assignment
  due tomorrow is visible as due soon; empty day has no empty headings; a
  student can add homework, plan it, start focus and mark Finished without
  the context menu; Export/Import are not in the week bar; the solve path is
  still `POST /api/solve`.

## spec.md changes on approval

- Required Behavior: Day view and the 800px default; Add homework fields;
  Plan my homework wording; workload numbers for a day.
- API: `GET /api/day`.
- Acceptance Criteria: Stage 2's "Complete when" path at 390px and 1280px.

## Out of scope

Copy/paste, duplicate day, copy routine, weekly routines, unfinished-work
review on week change (Stage 3). Month/year navigation (Stage 7). New theme
tokens. A per-account cutoff preference. Changing Stage 1 assignment, week,
changes or solve JSON. Executable and installer builds unless the owner asks.
