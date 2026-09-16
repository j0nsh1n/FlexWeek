# Contract: Stage 3 — reuse routines and recover past work

Status: approved 2026-09-14. The owner asked Codex to implement the
Claude-owned frontend portion and will have Claude review it afterward.

This contract is based on `claude/stage2-frontend` at `3b1f1c9`. Claude owns
the browser/desktop frontend. Grok owns persistence and authenticated API
work. Both clients continue to use the same HTML, CSS and JavaScript frontend.

## Goal

A student can reuse a normal school week without rebuilding it, adjust the
exceptions for the next week, carry unfinished homework forward exactly once,
and recover a schedule after a destructive change.

Stage 3 keeps three concepts separate:

- **Clipboard actions** are temporary editing tools in the current page.
- **Routines** are account-owned templates for reusable fixed commitments.
- **Restore points** are durable account-owned snapshots for recovery.

The existing 50-step Undo/Redo history remains the fast way to reverse recent
edits in the open page. It is not a durable backup.

## Owner decisions (proposed defaults)

These are recommendations. The owner can approve them together or replace an
individual choice before implementation.

1. Use an **internal clipboard**. Ctrl/Cmd+C and Ctrl/Cmd+V do not read or
   write the operating-system clipboard.
2. A copied homework session stays linked to the **same assignment**. A paste
   cannot plan more than that assignment's remaining unplanned minutes.
3. Do **not** offer “paste anyway” for a time collision. The preview lets the
   student choose another time, omit that item, or cancel.
4. A saved routine contains **fixed commitments only**. Homework is carried
   through the unfinished-work review, preserving its assignment identity.
5. Holiday, canceled-practice and different-school-day changes are edits in
   the **application preview**. They affect that destination week, not the
   saved routine, unless the student separately updates the routine.
6. Create restore points manually and automatically before **Clear week,
   Apply routine, and Restore**. Keep the newest **20** per account.
7. Restore points contain **weeks and assignments**. Preferences, routines,
   focus timer runtime state and the clipboard are outside the snapshot.

## 1. Copy, paste and duplicate

### Selection and controls

- Ctrl/Cmd+C copies the selected block. Ctrl/Cmd+V pastes into the current
  destination. Ctrl/Cmd+D duplicates the selected block.
- These shortcuts do nothing while focus is in an input, textarea, select,
  contenteditable element or open dialog.
- The block context menu exposes Copy and Duplicate. It also exposes Paste
  when the internal clipboard has a compatible item.
- A day action menu exposes Copy day and Paste day. Keyboard use is optional
  for day-level actions because they have visible controls.
- The internal clipboard is cleared on logout, account change and page reload.
  Its contents never cross accounts.

### Destination

- A fixed-block paste from the context menu targets the clicked calendar date
  and time. A homework-session paste targets the clicked date and remains
  flexible; the solver chooses its eventual time.
- A keyboard paste targets the selected occurrence's date and, for a fixed
  block, its start. If there is no occurrence selection, it targets the Day
  view date. If neither is available, it targets today when today is visible;
  otherwise paste is disabled with a short explanation.
- All starts and durations remain on the existing 15-minute grid. Week keys
  remain Monday dates.

### Identity and copied fields

- Every pasted or duplicated block gets a fresh block `id`.
- A fixed block keeps title, start, duration, category, course, priority,
  energy, lock state and Spotify URL. It resets `completed`, `completed_day`,
  `missed_days` and other historical outcome state.
- Copying one occurrence of a multi-day fixed block creates a one-day block.
  **Copy series** keeps all selected weekdays and maps them relative to the
  destination week. The UI always names which scope will be copied.
- A flexible homework session keeps `assignment_id` and copies current title,
  category and planning fields from that assignment. It gets a new session
  identity, resets session completion/history, stays `kind: flexible`, uses
  the destination as its candidate day and keeps `start: null`. A placed solve
  result is derived output and is never converted into a fixed block by copy.
- A homework paste is refused when its duration exceeds the assignment's
  current unplanned minutes. The preview offers the remaining duration when it
  is at least 15 minutes. Completed assignments cannot be pasted.
- Duplicate of a fixed block uses the same date and start as the source, so its
  preview normally reports a collision and asks the student to choose another
  time. Duplicate of homework adds another flexible session only when the
  assignment still has unplanned minutes.

### Copy day

- Copy day captures occurrences on one source date. Pasting maps those
  occurrences to one destination date, creates fresh block IDs and merges them
  with the destination day.
- Copy day never clears destination content.
- Completed homework, completion state, missed-day history and focus totals
  are omitted. Open homework sessions follow the same-assignment and remaining
  duration rules above.

## 2. Collision preview and atomic save

Every paste, duplicate, copy-day and routine application passes through one
preview model before it changes a week.

- A collision means two placed blocks overlap on the same calendar date.
  Adjacency is allowed.
- A fixed-item preview shows the source, destination date/time and any
  conflicting blocks. It offers Choose another time or Cancel. A flexible
  homework row instead shows its candidate date, duration and “Time chosen
  when you plan.”
- A batch preview lists every proposed occurrence. Conflicting and invalid
  rows start unchecked. The student may adjust a row's day/start, remove it,
  or cancel the batch.
- There is no force-overlap action in Stage 3.
- The preview validates the final week size before saving. A destination that
  would exceed 100 blocks cannot be confirmed.
- Confirmation writes all affected weeks and assignments once through the
  existing atomic `/api/changes` path. A validation, revision or network
  failure leaves the page and server unchanged.
- While a confirmation is pending, its button is disabled. Retrying the same
  confirmed operation after an unknown response must converge without making
  duplicate blocks. The client supplies a stable operation ID; the backend
  records or recognizes it as specified in the API section.
- A successful mutation is one Undo entry. Cancel and failed saves create no
  Undo entry.

## 3. Reusable weekly routines

### Routine contents

A routine is an account-owned named template containing fixed commitments.
Each template block has:

- `template_id`, unique within the routine;
- `title`;
- one or more weekday indexes, Monday = 0 through Sunday = 6;
- `start` and `duration_min`, both on the 15-minute grid;
- optional `category`, `course`, `priority`, `energy` and `spotify_url`.

Routine blocks are always locked. They do not contain assignment IDs, block
IDs, dates, completion, missed-day state, focus minutes, Pomodoro history or
solve output.

Limits: 50 routines per account, 80 characters per name and 100 template
blocks per routine. A routine itself cannot contain overlapping occurrences.

### Save and apply

- **Save week as routine** begins with the current week's fixed commitments.
  The student can uncheck items and name the routine before saving it.
- **Copy routine to…** is available from the week actions. It selects a saved
  routine and a destination week; Next week is the first shortcut. The student
  can apply every routine day or only the weekdays selected in the preview.
- Applying a routine creates fresh block IDs and maps weekday indexes into the
  selected Monday-keyed week.
- Before confirmation, the student can uncheck a holiday, remove one practice,
  or change a single school day's hours. These edits only affect the new week.
- The preview names each exception as “Only this week.” Editing the saved
  routine is a separate action with a separate save.
- Apply routine merges with existing blocks after collision review. It never
  clears a destination week.
- The apply request asks `/api/changes` to create a restore point for the
  schedule being changed in the same transaction. If that snapshot cannot be
  committed, application is aborted.

## 4. Unfinished homework review

- When a student first opens a week after an earlier week with unfinished
  assignments, show a non-modal **Unfinished homework** review.
- Each row is the existing assignment: same ID, title, exact due date/time,
  estimate, accumulated focus minutes, completion and revision. Stage 3 never
  creates a replacement assignment to carry work forward.
- The remaining amount is `max(estimate_min - focus_minutes - planned open
  session minutes, 0)` using the existing assignment planning rules.
- **Plan here** previews the remaining minutes and candidate days, then adds or
  adjusts flexible sessions in the destination week for the same assignment.
  Confirmation is an atomic save; Plan my homework chooses times afterward.
- Reopening the review or clicking Plan here again recalculates from current
  data. It cannot create more planned minutes than remain. A stable operation
  ID protects retries after an unknown response.
- Completed assignments and assignments with no remaining minutes are omitted.
  Overdue assignments remain visible with their real due date; the UI does not
  silently move the deadline.
- The review opens automatically once per destination week per page session.
  It remains available from the week actions afterward.

## 5. Restore points

### Behavior

- Restore points belong to the signed-in account. IDs are opaque; an ID owned
  by another account behaves as not found.
- A point snapshots all of that account's dated weeks and assignments in one
  transaction. It does not snapshot preferences, routines or ephemeral client
  state.
- The student can create a named restore point. The backend also creates one
  immediately before Clear week, Apply routine and Restore. If the automatic
  point fails, the destructive mutation does not run.
- Only the newest 20 points are retained. Pruning happens in the same
  transaction that creates the new point.
- Settings shows each point's label, creation time, week count and assignment
  count. It also states where data lives: **On this device** for the bundled
  local server or **On your FlexWeek server** for hosted mode.

### Preview and restore

- Opening a restore point first fetches a diff against current account data.
  The preview groups weeks and assignments into added, changed and removed
  counts, and lists affected week dates and assignment titles.
- The preview returns a state token for the exact current state it compared.
  Restore requires that token. If anything changed since preview, the server
  returns 409 and the frontend refreshes the preview.
- Restore first creates a point named `Before restore — <timestamp>`, then
  replaces the account's weeks and assignments from the selected snapshot in
  the same transaction.
- A failed restore rolls back both replacement and recovery-point creation.
  A successful restore returns current resource revisions.
- After success, the frontend clears Undo/Redo and the internal clipboard,
  stops a focus timer whose block or assignment no longer exists, reloads week
  and assignment caches, and keeps the closest valid week/day selected.

## 6. API contract for Grok

All routes require the existing session and CSRF protections. Limits are
validated server-side. JSON errors use the existing response shape.

### Routines

`GET /api/routines`

```json
{"routines": [{"id": "r-1", "name": "School week", "blocks": [], "revision": 1, "created_at": "...", "updated_at": "..."}]}
```

`PUT /api/routines/{id}` accepts `id`, `name`, `blocks`, and `revision`.
Revision 0 creates. An exact retry of an already-applied body succeeds without
another revision increase. A stale non-identical update returns 409. Success
returns the full routine object.

`DELETE /api/routines/{id}?revision=N` requires the current revision. An exact
retry after a successful delete is idempotent for the same account and
operation ID.

### Restore points

`GET /api/restore-points` returns `{"restore_points": [...]}` with summaries
only, newest first.

`POST /api/restore-points` accepts:

```json
{"label": "Before finals week", "operation_id": "client UUID"}
```

An exact retry returns the original full restore-point object. Labels are 1–80
characters.

`GET /api/restore-points/{id}/preview` returns:

```json
{
  "id": "rp-1",
  "state_token": "opaque",
  "changes": {
    "weeks": {"added": [], "changed": ["2026-09-14"], "removed": []},
    "assignments": {"added": [], "changed": [{"id": "a-1", "title": "Essay"}], "removed": []}
  }
}
```

`POST /api/restore-points/{id}/restore` accepts `state_token` and
`operation_id`. It performs the transactional recovery-point and replacement
rules above. Exact retries return the first successful result. A stale token
returns 409 without mutation.

### Atomic change operation ID

Extend `POST /api/changes` with optional `operation_id` and `snapshot_label`
fields for Stage 3 batch actions. An operation ID is a UUID. The server stores
the successful response per account and operation ID. Repeating the same ID
and identical payload returns that response; repeating the ID with different
content returns 409. When `snapshot_label` is present, the server snapshots
the account's current weeks and assignments before applying the changes in the
same transaction. Snapshot or change failure rolls back both. Existing callers
that omit both fields keep current behavior.

Successful operation records are bounded to the newest 1,000 per account.
Pruning happens inside a later successful operation; normal resource revisions
remain the backstop after an older operation record is pruned.

### Storage location

Add authenticated `GET /api/storage-info`:

```json
{"mode": "local", "label": "On this device"}
```

Hosted mode returns `{"mode": "hosted", "label": "On your FlexWeek server"}`.
The response reveals no filesystem path, host secret or database identifier.

## Ownership

- **Claude, frontend:** clipboard and shortcuts; visible block/day actions;
  collision/application previews; routine screens; unfinished-homework review;
  restore-point list/preview/restore flow; logout cache cleanup; frontend tests;
  and browser plus Qt WebEngine walkthroughs.
- **Grok, backend:** routine and restore-point tables, migrations and routes;
  operation-ID idempotency; transactional snapshot/restore; storage-info;
  ownership/revision/limit validation; backend tests.
- **GLM, helper:** adversarial contract and implementation review. The primary
  implementer checks every finding against source before accepting it.

## Acceptance criteria

1. Copying a Tuesday practice occurrence and pasting it next Tuesday previews
   the destination, saves a fresh one-day block, and leaves the series intact.
2. Copy day into a partly occupied day shows each collision and saves only the
   conflict-free checked items in one operation.
3. A student saves a school-week routine, applies it to next week, removes a
   holiday and shortens one school day in preview, then confirms without
   changing the saved routine.
4. Opening next week shows one unfinished Essay with its original assignment
   ID, exact deadline and progress. Repeated Plan here actions and request
   retries never duplicate the assignment or over-plan its remaining time.
5. Applying the routine creates an automatic restore point. Restoring an older
   point first preserves the schedule being replaced, then reloads both the
   browser and desktop client to the restored data.
6. A stale restore preview, failed snapshot and failed restore produce no
   partial state. Another account cannot list, preview, restore or infer the
   existence of the first account's routines or restore points.
7. All starts/durations remain divisible by 15, week keys remain Mondays,
   solver inputs stay pure, and existing `missed_days` recovery still passes.

## Verification

### Frontend

- Behavior tests for keyboard guards, occurrence/series scope, ID reset,
  assignment linkage, target selection and logout cleanup.
- Preview tests for adjacency, overlap, edit-to-resolve, unchecked conflicts,
  max-size rejection, one Undo entry, double-click and retry protection.
- Routine tests for fixed-only capture, exception edits and unchanged saved
  templates.
- Carry-forward tests for preserved identity/deadline/progress, overdue rows,
  repeat planning and completed omission.
- Restore tests for storage labels, diff display, stale-token refresh, cache and
  history reset, and vanished-timer cleanup.
- Real browser and Qt WebEngine walkthroughs at 390px and 1280px in both
  themes. Exercise save, reload and logout/login; do not substitute DOM-only
  tests for the final path.

### Backend

- Account isolation, CSRF, malformed input, limit and ownership tests for every
  new route.
- Revision and exact-retry tests for routines and `/api/changes` operation IDs.
- Transaction tests for snapshot failure, restore failure and stale preview;
  verify no partial rows and that the pre-restore recovery point is usable.
- Maximum-size snapshots and pruning to 20 points.
- Cross-week identity tests: Monday keys, 15-minute validation, one assignment
  across weeks and no duplicate carry-forward.
- Existing pure solver and `missed_days` recovery suites remain unchanged and
  green.

## `spec.md` changes on approval

- Required Behavior: clipboard scope, collision preview, fixed-only routines,
  unfinished-homework identity and durable restore semantics.
- API: routines, restore points, storage info and optional operation IDs.
- Storage: account-owned routine/restore data and retention.
- Acceptance Criteria: the complete student journey above.

## Out of scope

- System clipboard integration or copying between devices.
- Automatically syncing desktop-local and hosted databases.
- Sharing routines between accounts.
- Recurring database events beyond applying a routine to a dated week.
- Homework templates inside routines.
- Editing more than one destination week in one apply operation.
- Restoring preferences, routine definitions or active timer elapsed state.
- Google Calendar, LMS, OCR, AI chat or Qt custom painting.
- Packaging or producing desktop executables.
