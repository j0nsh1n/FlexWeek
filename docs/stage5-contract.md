# Contract: Stage 5 — make reminders and settings comfortable

Status: approved 2026-09-15 by the owner. Claude owns the browser/desktop frontend. Grok owns
persistence, authenticated API work, and the desktop autostart helper.
Both clients continue to use the same HTML, CSS and JavaScript frontend.

This contract is based on `feat/stage4-adaptive-plans` at `6ae893c`.

## Goal

A student can group settings, pick a timer preset without learning the
15-minute grid, preview an alert at a chosen volume, keep a quiet end-of-block
chime optional, see why web and desktop reminders differ, and return to a
remembered layout. Disabled sounds stay silent. The same block start fires at
most one reminder.

## Owner decisions (proposed defaults)

1. Settings sections are **Appearance**, **Focus**, **Notifications** and
   **Account**. Grouping is frontend. The preferences JSON stays flat.
2. Timer **presets** are Short (15/15/30), Standard (30/15/30) and Long
   (45/15/30), all 15-aligned, with long break every 4. Custom values still
   save. The countdown timer may use lengths that are not on the grid.
3. **Rounding** is explained, never silent. `POST /api/timer-split-preview`
   snaps each length to the nearest 15-minute step (0 becomes 15) inside the
   existing min/max, then returns the segment plan. `auto_split_pomodoro`
   requires already-aligned work and break lengths.
4. **Volume** is 0–100, default 80, matching Daily Scheduler. 0 is silent.
5. **End chime** defaults off. Start reminders stay the default alert.
6. **Test reminder** and **Preview alert** play locally. They do not write and
   they do not use the start-reminder idempotency key.
7. Web reminders need an open tab. The desktop app can alert from the tray
   after the window is closed. Spotify is a link; FlexWeek plays a built-in
   sound if the track does not play. `GET /api/reminder-limits` returns that
   copy so the two clients do not drift.
8. **Start at login** is stored on the account. The desktop shell applies it
   on supported Windows and Linux. Unsupported platforms keep the checkbox off
   and say so. The flag does not start a hosted browser session.
9. **preferred_view** (`week` or `day`), **sidebar_collapsed** and
   **sidebar_width_px** persist on the account. Empty/default values are
   omitted, so existing clients keep working. When `preferred_view` is omitted,
   the Stage 2 breakpoint still chooses Day at 800px and Week when wider.
10. Restore points still omit preferences (Stage 3). Comfort fields follow
    that rule.

## 1. Comfort fields on preferences

GET/PUT `/api/preferences` (defaults omitted when they match the values below):

- `alert_volume`: 0–100, default 80.
- `end_chime`: bool, default false.
- `tray_notifications`: bool, default true. Desktop tray balloons follow this.
  In-app toasts still follow `reminder_sound` / `reminders_enabled`.
- `start_at_login`: bool, default false.
- `preferred_view`: `week` or `day`, or omitted.
- `sidebar_collapsed`: bool, default false.
- `sidebar_width_px`: 200–640, or omitted.

`auto_split_pomodoro` true with a work, break or long-break length that is not
a positive multiple of 15 returns 422.

## 2. Timer split preview

`POST /api/timer-split-preview` is authenticated and CSRF-protected. It does
not write.

```json
{
  "duration_min": 90,
  "timer_work_min": 25,
  "timer_break_min": 5,
  "timer_long_break_min": 15,
  "timer_long_break_every": 4
}
```

`duration_min` is optional. When present it is 15–7140 and already on the grid.
Timer fields use the same min/max as preferences.

Response:

```json
{
  "timer_work_min": 30,
  "timer_break_min": 15,
  "timer_long_break_min": 15,
  "timer_long_break_every": 4,
  "rounded": true,
  "message": "Work length 25 minutes becomes 30 on the 15-minute grid. Break length 5 minutes becomes 15 on the 15-minute grid.",
  "segments": [],
  "total_min": 0
}
```

When `duration_min` is present, `segments` match today's frontend split
(work chunks, then a break after each work chunk except the last, long break
every N work chunks) and `total_min` is their sum. `rounded` is true when any
timer length changed.

## 3. Presets and reminder limits

Authenticated GET `/api/timer-presets`:

```json
{
  "presets": [
    {"id": "short", "label": "Short", "timer_work_min": 15, "timer_break_min": 15, "timer_long_break_min": 30, "timer_long_break_every": 4},
    {"id": "standard", "label": "Standard", "timer_work_min": 30, "timer_break_min": 15, "timer_long_break_min": 30, "timer_long_break_every": 4},
    {"id": "long", "label": "Long", "timer_work_min": 45, "timer_break_min": 15, "timer_long_break_min": 30, "timer_long_break_every": 4}
  ]
}
```

Authenticated GET `/api/reminder-limits`:

```json
{
  "web_open": "Reminders fire in this browser only while FlexWeek is open in a tab.",
  "desktop_background": "The desktop app can still alert from the tray after the window is closed.",
  "spotify": "A Spotify link is best-effort. FlexWeek plays a built-in sound if the track does not play.",
  "duplicate": "The same block start fires at most one reminder until it is handled or the day changes."
}
```

## Out of scope

- Grouping the Settings dialog, Test/Preview buttons, volume slider, sidebar
  drag, and reminder-limit sentences in the page (Claude).
- Applying start-at-login and tray Test from the Qt shell (desktop follow-up
  on this contract; the preference is stored now).
- Changing sleep, accounts, restore-point contents, or the solver.
- Spec.md edits until the owner approves this contract.

## Verification (backend)

- Default GET `/api/preferences` still matches the Phase 7 exact object.
- Comfort fields round-trip; defaults stay omitted; volume 101 and sidebar
  width 50 are 422.
- `auto_split_pomodoro` with a 25-minute work length is 422; 45-minute work
  with split on still saves.
- Split preview snaps 25/5 to 30/15 and, for a 90-minute task, returns the
  same segment total the current frontend plan would after that snap.
- Preset ids and reminder-limit sentences match this file.
- Unauthenticated GET of the new routes is 401.
- `.venv/bin/python scripts/verify.py --web-only` from this worktree.

## Addendum 2026-09-22: alarm sound, planning style and setup progress

Three preferences join `comfort_json`. Each is omitted from `GET /api/preferences`
while it holds its default, so older clients read an account unchanged.

- `alarm_tone` is one of `chime`, `soft`, `bright`, `low`, `glass`, or `spotify`,
  default `chime`. It is the sound for reminders, the end of a focus session, and
  a new alarm. `spotify` opens `default_spotify_url` when the alert fires.
- `planning_style` is one of `auto`, `suggest`, or `manual`, default `suggest`.
  `auto` gives new homework a time as it is added. `suggest` is the behaviour
  before this addendum, where homework waits until Plan my homework. `manual`
  leaves homework waiting for the student to drag it onto the calendar.
- `setup` is `{version, step, finished_at}` or absent. `version` is 1 to 100,
  `step` is 0 to 20, and `finished_at` is `YYYY-MM-DDTHH:MM` or null. A finished or
  skipped setup sets `finished_at`, and the desktop never shows setup again unless
  the student asks.
