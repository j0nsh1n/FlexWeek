# spec.md changes for 0.15, for Jonathan's approval

`spec.md` still describes the app before 0.15's decisions (`docs/0.15/plan.md`, "Decisions"). Nothing
below is applied; each row is a passage as it stands and the wording proposed for it. Grok's earlier
draft of the same edit was lost with its worktree on 24 September, so this is redrafted from the
decisions and the code as built. Approve, change, or strike each row; then Claude edits `spec.md`
in one commit.

| spec.md passage | As it stands | Proposed |
| --- | --- | --- |
| Solver rules, "places every flexible block on the 15-minute grid (Mon–Sun, 06:00–23:00)" | 06:00–23:00 | "on the 15-minute grid (Mon–Sun, 00:00–24:00), inside the account's work windows" |
| Solver rules, "Sleep (23:00–06:00) is a guard the solver never places into and never steals." | A fixed sleep guard | "Work windows bound where the planner places homework. Until the student sets any, the whole day is open, and the planner ranks the night (23:00–06:00) last, so it is used only when the rest of the day is full. Placing a block by hand at any hour is always allowed." |
| Day view, "time still free before 23:00" | 23:00 | "time still free before midnight" |
| Preferences, "up to 21 `protected` windows ... up to 21 soft `study_windows`" | No work windows | Add: "up to 21 `work_windows`, the hours the planner may use, set in setup and in Settings; `work_windows_defaulted` marks an account that has not chosen any, whose whole day is open. Study windows are set in Settings only." |
| Month view paragraph | Deadlines, projects, study time; a date opens Day | Add: "Each date lists its timed blocks as chips that start with their time ("09:00 History essay"), from the month reply's per-date `blocks`; the open week, and any week left with unsaved changes, are drawn from what the student has now. A chip can be dragged to another visible date and keeps its time; one occurrence of a repeating block moves alone; a drop the deadline refuses leaves the chip where it was and says why. Homework due that day is listed first." |
| Validation, "Explicit starts are on the visible grid and end by 23:00. An assignment's `due` is a naive local `YYYY-MM-DDTHH:MM`" | Ends by 23:00; due always has a time | "Explicit starts are on the visible grid and end by 24:00 (a block ending at midnight is stored as the next date at 00:00). An assignment's `due` is a naive local `YYYY-MM-DD`, due by the end of that day, or `YYYY-MM-DDTHH:MM` for work due at a set time that day" |
| Time handling, "Slot grid: Mon–Sun 06:00–23:00, 15-minute slots, 68/day × 7 = 476/week." | 476 slots | "Slot grid: Mon–Sun 00:00–24:00, 15-minute slots, 96/day × 7 = 672/week." |
| Views: Week and Day (wherever the fixed-height week is described) | Week fits the day on screen | Add: "Hours scroll, and the student can zoom: Ctrl and the wheel, Ctrl with =, - and 0, or two buttons beside the hours. Each surface's level is remembered per device in the look file. Time snaps to 15 minutes; overlaps are allowed, drawn side by side and named; a block moved by hand is pinned; a refusal leaves the block where it was and says why. Every design draws its own Day and Week on one shared gesture engine (`docs/0.15/architecture.md`)." |
| GitHub Actions paragraph and "Verification" section, "`--backend-only` ... It installs nothing and does not build a binary." | CI is backend-only | Add: "A second job, `rig`, installs Xvfb, Openbox and xdotool, runs Today's app's Day and Week with a real pointer on a hidden display, and uploads the screenshots, videos and results. The backend job is unchanged." |
| Acceptance, "A student opens Month, sees deadlines with planned and completed study time" | | Add a line: "A student drags a Month chip to another date and the block moves there with its time; dragging it past its due date is refused in words." |

Not proposed: the solver's reason codes (`SLEEP_GUARD` stays as the name of the night-ranked-last
rule unless Grok renamed it; check `backend/solver.py`), the pomodoro rules, and anything about
Windows builds.
