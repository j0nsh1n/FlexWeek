# 0.15 issues, one list

Everything found by using the app: Jonathan (`owner-findings.md`), Timmy and AL (their agreed
list, numbers T1 to T36), Claude (`audit-02.md`, C1 to C17), and ChatGPT's screenshots
(`evidence/ux-audit-01/`). Same thing found twice is one row. Each row says what is wrong, where it
is known, and its state. Priorities: P1 ships fixed; P2 fixed if it fits; D needs Jonathan's
decision first.

## Reminders and alarms

| # | What | Where / evidence | State |
| --- | --- | --- | --- |
| 1 | A block saved inside its own lead time never gets a reminder: the fire time is already past. Nothing fires at the start itself. | `remind.py` `start_alert_due`: fires only when `now - 2 <= start - lead <= now`, polled every 30 s. Clock-held probe: a block saved at 17:02 for 17:15 with lead 5 fires at 17:10; saved at 17:12 it never would. T1, owner 5. | P1 |
| 2 | Timmy's clean test got no alert (block for 18:45, lead 10, nothing by 18:48) and the cause is unknown. Reminders are off after a skipped setup (`reminders_enabled` False) and the switch is easy to miss (row 30). | T1, C-reminder probe. Needs a run with the real desktop notification watched, not just the signal. | P1 |
| 3 | "Saved preferences." overwrites a reminder shown in the status bar. | `controller.py:2752`. T1. | P1 |
| 4 | A block's Spotify link never plays by itself; only the alarms in Settings > Alerts do. Dragged blocks have no reminder switch of their own. | T2, owner 5. Not a bug today; a rule to decide: play the block's link when its reminder fires? | D |

## Times and the grid

| # | What | Where / evidence | State |
| --- | --- | --- | --- |
| 5 | The block editor accepts any minute and the server refuses anything off the 15-minute grid after Save, in its own words ("block must fit the 00:00–24:00 grid"). Setup rounds times silently. Elsewhere steps of 5. | `widgets.py` `_span_problem` checks the length only; API: 18:30 and 18:45 save, 18:35/18:37/18:40 are 422 (`scratch/grid_probe.py`). T6, owner 1, C8. Decision 7 says 15 minutes: Start and End step by 15 and a typed time snaps as the box is left. | P1 |
| 6 | New homework is due on the week's Monday, not today. | `widgets.py:913` `"due": due or week_start`. T4, owner 6, C1. | P1 — fixed `225908e`: new homework defaults to today. |
| 7 | Changing the due date raises inside Qt and the follow-up step (`_disable_spread`) never runs. | `DueField`: `self.date.dateChanged.connect(self.changed.emit)` hands a `QDate` to a `Signal()`; seen as `TypeError: changed() only accepts 0 argument(s)` in Claude's probe. T5. | P1 — fixed `7b9d19b`: the signal emits without a `QDate`, and the follow-up runs. |
| 8 | Plan places homework on days already gone (a Monday-due report planned on the past Tuesday). | T3. The solver plans the whole visible week; nothing tells it today. | P1 — fixed `e123f55`: Plan excludes time before now, including in Replan all. |
| 9 | Homework length: 0 quietly becomes 60, 99 hours is accepted. | T11. | P1 — fixed `8709df9`: lengths outside 15 minutes to 24 hours are refused in words. |
| 10 | Mission's Day and Week open at midnight; Timmy also saw Day and Week open at the wrong hours elsewhere. | `mission.py` has no `scroll_to`; the others scroll to now or the first block. C2, T27. | P1 |

## Words on screen

| # | What | Where / evidence | State |
| --- | --- | --- | --- |
| 11 | The More menu and Advanced items, Plan my homework / Suggest times and the plan controls have no hover descriptions; "Unfinished" is greyed with no reason; Quick focus is unexplained. | `window.py:683` `addAction(button.text())`, no tooltips. T8, T23, owner 4, C10. | P1 |
| 12 | Unfinished sometimes does nothing, sometimes opens an empty screen. | T7. | P1 |
| 13 | Cancelling Running late leaves its preview message on screen. | T9. | P1 |
| 14 | Sign-in shows one error for every problem; sign-up says nothing for an empty password. | T10. | P1 |
| 15 | Settings says "FlexWeek 0.14.3". | `desktop/native/version.py`. T14, C6. Release step. | P1 |
| 16 | "in 20m" / "in 20 min" / "IN 20 MIN"; "Finished" and "Done"; "Not placed yet" and "Needs a time" for the same tray. | T24, T25, C13. One word each. | P2 |
| 17 | The block editor's title "Edit fixed commitment"; "This day was missed"; the plain "Next:" strip under the title with no label. | T19, C14. | P2 |
| 18 | Settings words: volume with no %, "Long break after 4" with no unit, "Stay in the tray", "Keep alerts visible until handled", the Spotify placeholder cut off, Account… and Availability… under This computer. | T16. | P2 |
| 19 | The sound test says "No sound card" and nothing else. | T33. | P2 |
| 20 | Account: "On this device" with no full stop. | C17. | P2 |

## Drawing and layout

| # | What | Where / evidence | State |
| --- | --- | --- | --- |
| 21 | Chips cut their text at the wrong end ("Science poster · 1 h …"); the top bar clips below about 900 px ("21 – 2…", "n my homew"); Retro's notepad clips its deadline lines at 1150x768 with large text. | C5, C7, C9, T28. | P1 |
| 22 | A short block on sideways hours draws as three lines of "…". | Shared painter `words`. C3. | P1 |
| 23 | The first and last hour labels are cut at the scroll edges on sideways hours. | Shared `hour_labels`. C4. | P2 |
| 24 | The date picker is cut off on the left in setup and on the right in Add homework. | T29. | P2 — fixed `85c5312`: the whole month fits and the popup stays on screen. |
| 25 | The "Next: … (in 23m)" countdown only redraws during a focus session. | T22. | P2 |
| 26 | A one-off dragged block's editor shows seven day boxes with nothing saying that ticking one makes it repeat. | T20. | P2 |
| 27 | Save and Cancel look the same; floppy-disk and red-X icons look dated. Delete is the most prominent button in the block editor. | T21, T13. | P2 |
| 28 | Retro shows the same "no time yet" chips in deadlines.txt and at the foot of the main window. | C15. | P2 |
| 29 | Settings > Appearance & layout is dense: an implementation note first, a box in a box, style rows in a grey table. Scrolling over its number boxes changes them. | T15, owner 2, C11. | P2 |
| 30 | Settings > Alerts: alarm sound and reminders mixed, the Reminders switch off and easy to miss among live-looking controls, two "Chime" dropdowns, no sign of when an alarm rings. | C12. | P2 |
| 31 | Dark themes have weak contrast; the layout choice is not explained; My day and Month are unclear to a first-time user. | T30, T31. | P2 |
| 32 | Ctrl and = zooms only when the hours have keyboard focus. | `canvas.py` `keyPressEvent`; T32. Make it the window's. | P2 |
| 33 | A dragged block counts toward School in the Day summary. | T26. Category of a drag-made block. | P2 |

## Actions and safety

| # | What | Where / evidence | State |
| --- | --- | --- | --- |
| 34 | Dragging or resizing saves at once with no sign; add an Undo toast as after finishing homework. Advanced actions give no feedback. | T17, T18. | P2 |
| 35 | Plan cannot be undone. | T12. Check: a plan is a save, and saves are undo steps; if Undo is there and hidden, that is row 34. | P2 — fixed `1c6d3e6`: Plan and Replan all each save as one Undo step and show an Undo notice after the save lands; automatic planning joins Add homework's step. |
| 36 | Log out and Delete account have no confirmation. | T13. | P1 |

## Help, setup and docs

| # | What | Where / evidence | State |
| --- | --- | --- | --- |
| 37 | No Help or About; a tutorial and guides are for later, but the app should say so somewhere. | T8, owner 3. | P2 |
| 38 | README does not list the Qt system libraries (libEGL.so.1 first) or separate runtime from dev needs; DESKTOP.md is stale near line 170; the 0.15 release notes are a draft. | T34, T35, T36. Release step. | P2 |

## Jonathan's decisions (24 September)

1. **A block's Spotify link plays by itself** (row 4). It plays at the block's start, the way an
   alarm does, and stops the way an alarm is stopped.
2. **Blocks remind by default** (rows 1 and 2). The reason no notification came is that reminders
   are off after setup and the switch is buried in Settings > Alerts. Reminders are on for every
   block unless the student turns them off; a block saved inside its lead time reminds at once; the
   switch moves to the top of Alerts. Timmy's failed 18:45 test is still chased down on its own.
3. **Times are by the minute; dragging steps by 5** (row 5, replaces decision 7's 15-minute
   snap). A typed Start or End keeps any minute, and the server stores it. Dragging, resizing and
   creating by drag snap to 5 minutes by default, and setup and Settings offer 5 or 15. The
   planner still gives homework quarter-hour starts, fitted around blocks at any minute.
4. **Delete in the block editor** (row 27), Claude's call: it leaves the button row, becomes a
   quiet text button at the bottom left, and asks before deleting. Save is the one filled button.

## Fix plan

Four lanes that touch different files, so they can run at the same time; each ends in its own
tests and the rig.

- **A. Minute times** (decision 3; rows 5, 9): backend validators and `span_fits_day` accept any
  minute while keeping each field's length limits; the solver's occupancy covers partly-filled
  quarter hours; `snap()` takes the step from a new `drag_step_min` preference (5 or 15); setup
  and Settings offer it; the rig's
  quarter-grab and snap expectations follow the step. Backend and engine.
- **B. Reminders and alarms** (decisions 1 and 2; rows 1 to 4): reminders on by default and for
  existing accounts, a reminder at once when saved inside the lead, the block's Spotify link played
  at its start, the status line kept, and Timmy's case reproduced with the desktop notification.
  Controller, `remind.py`, alerts, Settings > Alerts.
- **C. Homework and planning** (rows 6 to 8, 35): due date defaults to today, the `DueField`
  signal, planning never on past days, length limits, Plan undoable.
- **D. Screens and words** (rows 10 to 34, 36, 37): tooltips and reasons, Unfinished, Running late,
  sign-in errors, confirmations, the block editor's buttons and title, chips and the top bar,
  sideways painter fixes, Mission's first scroll, Ctrl and = everywhere, Settings layout and words,
  the version, README and DESKTOP.md.
