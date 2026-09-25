# Jonathan's findings from using 0.15 (24 September)

From the test copy at `4e1186c`, Timeline design, Night colours. Held until the other agents' audits
are in; then fixed together. Claude's notes under each are from a read of the code, not proven.

1. **Setting a time by hand moves in steps of 5 minutes.** The block editor's Start and End are
   `QTimeEdit`s (`desktop/native/widgets.py`, `blockStart`). A student typing a time should be able to
   set any minute; the grid snaps drags, not typed times. Check the homework editor's time too.
2. **Settings feels dense and cluttered** (Appearance & layout shown: the explanation paragraph,
   Animations, the fine-tune box, then "Main view" with its own box of dropdowns, all in one column).
   A layout pass, not new features.
3. **A tutorial and guides, later.** Footnoted here for now; not in 0.15's scope.
4. **Hover descriptions.** Every action in the More menu (Add homework, School hours, Add fixed time,
   Running late, Unfinished, Routines, Quick focus, Open Spotify link, Replan all my homework,
   Advanced, Log out) and the "Plan my homework" / "Suggest times" button should show a short
   description on hover.
5. **No alarm and no notification when a block made by dragging started.** The block was dragged in
   at 17:15–17:45 with a Spotify link, while the clock was about 17:00; nothing rang or popped up.
   Claude's read: block reminders come from `_reminder_blocks` in the controller, a copy of the week
   fetched separately (`controller.py` near line 2652), so a block saved a moment ago may not be in
   the copy the reminder check reads until the next fetch. To verify with a clock held near a
   block's start. Also: a block's Spotify link is opened by hand from the block; only the alarms in
   Settings > Alerts play a song by themselves. If a block with a link should play it at its start,
   that is a new feature to decide on.
6. **Adding homework should default the due date to today**, not to whatever the date box starts
   at.

Reported by Jonathan; more to come from him and from the other agents' audits.
