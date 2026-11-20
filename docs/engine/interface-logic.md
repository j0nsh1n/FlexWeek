# Logic that stays in the interface

The Rust engine owns planning, storage and the Qt-free desktop helpers. The
Material interface is Qt Quick/QML with Python bridges and a small Python shell.
This file maps the decisions left there and the test areas that cover them. It
replaces the v0.17.2 Widgets inventory; it is a current module map, not a second
product contract.

QML files decide presentation, keyboard focus and which bridge action a control
calls. Python bridges read `NativeSession`, validate drafts and expose plain
state to QML. QML does not call HTTP, SQL or the engine directly. The session
and window still make calls and manage application lifetime, so not every
interface-side decision is a candidate for the pure engine.

## Application controller: `desktop/native/window.py`

`NativeWindow` is a QObject controller, not a QWidget window. It owns
`MaterialPage`, the `QQuickView` defined in `desktop/native/material/host.py`.
Qt Quick paces that view's frames to the screen.

| Area | What the controller decides | Tests |
|---|---|---|
| Material lifetime | When to build, load, publish and dispose the Material page; how a load or scene-graph error reaches the drawing fallback | `desktop/tests/day/test_material_shell_fallback.py`, `desktop/tests/test_material_window.py` |
| CPU drawing | On a graphics failure, save `cpu_drawing_version`, save unsaved edits and start one software-drawing copy; on a second failure show Quit and Try again | `desktop/tests/day/test_material_shell_fallback.py`, `desktop/tests/account/test_material_sign_in_and_create_account.py` |
| Account and setup | When sign-in, recovery and setup cover Material; when setup resumes and when it finishes | `desktop/tests/account/`, `desktop/tests/e2e/` |
| Save lifetime | When autosave runs, when a failed save is retried, and what closing or signing out must wait for | `desktop/tests/week/`, `desktop/tests/account/` |
| Alerts and alarms | When reminders and alarms are presented, which sound or Spotify link plays, when sound stops, and when no pop-ups or "Leave reminders on screen" keeps a reminder card with Snooze and Close | `desktop/tests/planner/`, `desktop/tests/settings/`, `desktop/tests/sheets/` |
| Updates | Daily check cadence, manual checks, download state and when an update sheet may open over another sheet | `desktop/tests/updater/`, `desktop/tests/sheets/test_material_info_sheets.py` |
| Sync and tray | When the sync service starts, when a phone change refreshes Material, and when closing hides to the tray or quits | `desktop/tests/sync/`, `desktop/tests/e2e/` |

`desktop/main.py` applies a saved software-drawing choice before the first Qt
Quick window is made. `desktop/native/cpu_drawing.py` builds the relaunch
command for a source run, packaged executable or AppImage.

## Shared session: `desktop/native/controller.py`

`NativeSession` remains the interface's owner of live account and week state.
Material bridges use this one session rather than making their own planner or
store.

| Decision group | What it covers | Tests |
|---|---|---|
| Loading and saving | Draft parking, revision conflicts, retries, operation ids and save rollback | `desktop/tests/week/`, `desktop/tests/e2e/` |
| Homework and blocks | Add/edit/delete, completion, repeat occurrences, pins and copy/paste previews | `desktop/tests/sheets/`, `desktop/tests/week/` |
| Planning | Solve previews, Replan all, Place now, Running late, Spread and placement refusals | `desktop/tests/planner/`, `desktop/tests/week/` |
| Undo and redo | When history is allowed, stale steps, changes that cross stored weeks, and restore-point Undo for a change from this week on | `desktop/tests/week/`, `desktop/tests/planner/`, `desktop/tests/sheets/` |
| Focus | Start/replace, pause, phase advance, early ending, credit and auto-completion | `desktop/tests/focus/` |
| Alerts | Reminder and alarm queues, kept reminder cards, snooze, Spotify fallback and focus muting | `desktop/tests/planner/`, `desktop/tests/settings/` |
| Preferences and hours | Preference merges, availability validation, week start and planning style | `desktop/tests/settings/` |
| Restore and transfer | Restore-point create/preview/apply and account import/export | `desktop/tests/account/`, `desktop/tests/sheets/test_material_manage_sheets.py` |
| Session | Kept sign-in, recovery, password change, logout and expiry cleanup | `desktop/tests/account/`, `desktop/tests/e2e/` |

## Material bridge modules: `desktop/native/material/`

| Module | Interface decision | Tests |
|---|---|---|
| `bridge.py` | Screen navigation, Open on once per sign-in, shared theme state, snackbars, Retry save and shared keyboard actions | `desktop/tests/day/`, `desktop/tests/settings/` |
| `bridge_week.py` | Week rows and drawer state, planning, Place now, block placement, copy and paste | `desktop/tests/week/`, `desktop/tests/planner/` |
| `bridge_day.py` | Day agenda, current/next work and day navigation | `desktop/tests/day/` |
| `bridge_month.py` | Month cells, deadlines and date navigation | `desktop/tests/month/` |
| `bridge_myday.py` | My day's current, next and completed rows | `desktop/tests/myday/` |
| `bridge_focus.py` | Focus screen state and controls from the one session timer | `desktop/tests/focus/` |
| `bridge_account.py` | Sign-in/create/reset, recovery acknowledgement, three setup steps, card choices, detailed-control visibility and preview contents | `desktop/tests/account/`, `desktop/tests/e2e/` |
| `bridge_settings.py` | Preference state and writes, preset and advanced drafts, Simple/More/All, saved looks, alerts, focus, phone and sync controls | `desktop/tests/settings/`, `desktop/tests/sync/` |
| `bridge_hours.py` | Study, protected and school hour drafts: 15-minute times, day selection, end order, protected overlap and the 21-row limits | `desktop/tests/settings/test_material_hours_drafts.py`, `desktop/tests/settings/test_material_settings_4a.py` |
| `sheet_block.py`, `bridge_sheets.py` | Sheet kind and state, edit drafts, weekly fixed times and Until, repeat scope questions, doubled-week notices, restore-point Undo, More actions, Help/About/Update and sign-out routing | `desktop/tests/sheets/` |
| `bridge_manage.py` | Account and restore forms, import and delete questions, restore preview state | `desktop/tests/sheets/test_material_manage_sheets.py` |
| `bridge_alarms.py` | Alarm drafts and the 20-alarm/day/link rules; ring-screen Dismiss and Snooze | `desktop/tests/settings/test_material_alarms_4b.py` |
| `bridge_info.py` | Help, About and Update display state from release, storage and updater facts | `desktop/tests/sheets/test_material_info_sheets.py` |
| `theme.py` | Preset schemes, one-mode looks, accent, fonts, local look parsing, advanced defaults, tiers, import/export and readability fixes | `desktop/tests/settings/`, `desktop/tests/settings/test_material_tokens.py` |
| `host.py` | The `QQuickView`, QML loading, initial bridge property, scene-graph error reporting and device/Material appearance resolution | `desktop/tests/day/`, `desktop/tests/settings/test_material_appearance_own_state.py` |
| `dynamic_color.py` | Platform accent reading and the engine's Material scheme call | `desktop/tests/sheets/test_material_dynamic_color.py` |

## QML decision points: `desktop/native/material/qml/`

| Area | What QML decides | Tests |
|---|---|---|
| `Main.qml` | Rail or bottom bar, modal key guards, Add choices, screen shortcuts, focus return and which overlay is above another | `desktop/tests/day/test_material_shell_keys.py`, `desktop/tests/day/test_material_week_keys.py` |
| `views/` and `week/` | Screen arrangement, homework drawer and card actions | `desktop/tests/week/`, `desktop/tests/day/`, `desktop/tests/month/`, `desktop/tests/myday/` |
| `hours/HoursPane.qml` and `week/WeekBlock.qml` | Pointer and keyboard gestures, menus, drag previews, and Ctrl+C/Ctrl+D/Delete on the focused block | `desktop/tests/week/`, `desktop/tests/day/test_material_week_keys.py` |
| `account/` | Sign-in/create/reset fields, recovery acknowledgement and which account layer covers the shell | `desktop/tests/account/` |
| `setup/` | Three card steps, when detailed controls show, and a live preview containing only entered school, activities and study hours | `desktop/tests/account/test_material_setup_cards.py`, `desktop/tests/e2e/` |
| `settings/` | Section controls, timer and hour editors, and the Simple/More/All control sets | `desktop/tests/settings/` |
| `sheets/` | Sheet focus, discard and confirmation flows, alarm editing and ringing, account and restore actions | `desktop/tests/sheets/` |
| `focus/` | Full-window timer presentation and which controls belong to the running phase | `desktop/tests/focus/` |

## Other interface-side Python

These modules stay because they touch Qt, the process environment, sound,
files or external programs, even when their rules are plain data:

| Module | Role | Tests |
|---|---|---|
| `client.py` | Allowed API paths, request epochs, cookies and student-facing HTTP errors | `desktop/tests/e2e/`, `desktop/tests/account/` |
| `kept_alerts.py` | Kept reminder cards and the focus-notice strip, following the clock and moved, deleted or renamed blocks | `desktop/tests/planner/`, `desktop/tests/settings/` |
| `settings_copy.py`, `account_copy.py`, `sheet_rules.py`, `setup_steps.py` | Shared wording and Qt-free setup/settings rules, kept out of the removed Widgets modules | area suites for the caller |
| `fields.py`, `hours/scale.py`, `hours/geometry.py` | Week-start state, drag steps, zoom scales and shared time helpers | `desktop/tests/week/`, `desktop/tests/settings/` |
| `updater.py` | Safe download and install swapping | `desktop/tests/updater/` |
| `autostart.py`, `kept.py` | Login entry and private kept-session file | `desktop/tests/settings/`, `desktop/tests/account/` |
| `spotify.py`, `tones.py`, `sound.py` | Spotify outcome, tone synthesis and safe audio output | `desktop/tests/settings/`, `desktop/tests/planner/` |
| `work_windows.py` | Study-hour presets and the availability limit shared with Material | `desktop/tests/settings/` |

## Engine boundary

A decision that needs no Qt object, file, clock, network or environment belongs
in the engine when it is shared planning or storage logic. Presentation state,
QML focus, draft controls and process lifetime stay here. New Python adapters
only encode, call and decode; they do not grow a second implementation of an
engine rule.
