# Material 3

Material 3 is the desktop app's only student interface. It is Qt Quick/QML hosted
from Python; there is no style switch, design picker, look editor or Ctrl+K
command bar. Sign-in, recovery codes, setup, the planner screens, Settings,
Focus, alarms and the app's sheets all use Material.

## Shell and screens

`desktop/native/material/host.py` defines `MaterialPage`, a `QQuickView` that
loads `desktop/native/material/qml/Main.qml`. The QObject controller
`NativeWindow` in `desktop/native/window.py` owns the view. `QQuickView` paces
frames to the screen; two five-second checks on a 360 Hz screen measured 360.0
and 349.1 frames a second. The shell has a navigation rail, or a bottom bar
under 768 px, a top bar and a snackbar. `qml/views/` contains Week, Day, Month,
My day and Settings. Week's homework list is a drawer on the right, or below
the grid at phone width. Focus is a full-window overlay in
`qml/focus/FocusScreen.qml`.

Week opens when `preferred_view` is omitted. Settings > Planning > Open on can
instead choose Day, Month or My day; the choice applies once per sign-in. The
Add button offers Add homework and Add fixed time. More contains the planning
and account actions, including Copy day, Copy last week's fixed times, Copies of
this week, Reload this week and, when a link is saved, Open Spotify link.

Ctrl+N adds homework and F1 opens Help. Ctrl+Shift+L opens Week as a list.
Ctrl+C, Ctrl+D and Delete copy, duplicate and delete the block with keyboard
focus; Delete asks first. Ctrl+Z undoes and Ctrl+Shift+Z or Ctrl+Y redoes.
Number keys 1–5 have their own switch, on by default. The letter keys have a
second switch, off by default: T, D, W, M, J, K, C, P, Z and F. These shortcuts
do not act while typing or while a sheet, Focus, an account screen or another
modal layer has the keyboard.

## Bridges and session

QML reads and changes the week through `MaterialBridge` and its screen bridges;
the bridges use `NativeSession`. QML does not touch HTTP, SQL or the engine.
`bridge.py` holds navigation, appearance and shared actions. Week, Day, Month,
My day, Settings, account/setup, sheets, alarms and focus have their own bridge
modules. `SheetHost.qml` chooses the Material sheet for editing, routines,
alarms, Help, About, Update, Manage account and Copies of this week. The ring
screen sits above sheets and Focus.

The Rust session in `engine/app/src/session/` owns request delivery, account flows, status, autosave
and the decisions made before closing or signing out. `NativeSession` and the Python shell still hold
the live week and the undo, planning, focus, reminder and alarm rules that have not moved yet. They do
not maintain a second planner or timer. PR #181 is moving more of those rules into Rust; see
`ARCHITECTURE.md` for its status.

## Look and settings

`theme.py` builds the `theme` object from `tokens.json`: Material colour roles,
ink aliases, category colours, density and contrast. The presets are Slate,
Blue, Sea, Forest, Gold, Rose, Plum, High contrast, Paper, Ink and Terminal.
Slate is the default. High contrast, Paper, Ink and Terminal keep their own one
mode; the other presets follow System, Light or Dark. An account accent can sit
on top of a preset, except High contrast's fixed yellow. Font is Sans (Inter),
Serif (Newsreader headings over Inter) or Mono (JetBrains Mono).

The look file's `material` object holds `preset`, `mode`, `contrast`, `density`,
`shortcuts`, `letters`, `advanced`, optional `font`, optional `saved` looks and
optional `lookTier`. Settings > Look > Advanced settings has Simple, More and
All. Simple holds the preset, mode, corner shape, block style, row size and text
size. More adds the layout and grid dials. All adds the colour codes and
readability check. Changing tier never changes a value; `lookTier` is kept on
this computer and starts on All after a setup that used the detailed controls.

Settings has Look, Planning, Focus, Alerts and This computer. Planning includes
Open on, planning style, study and school hours, planner rules and drag step.
Focus includes Short, Standard, Long and Custom timer lengths. Alerts includes
reminders, sounds, alarms and tray behaviour. This computer includes account,
setup, updates, keyboard switches, phone pairing and sync. Report a problem opens Jonathan's Google form
in the browser, with the FlexWeek version and computer details filled in.

Animations are Off, Reduce, Normal or More. Reduce keeps short fades without
travel. More takes 2.5 times Normal's durations and travels four thirds of
Normal's distances. Advanced Motion speed multiplies durations by 1.5 for
Slower or 0.6 for Faster; its Off choice stops animation. Material's Qt Quick
window paces these animations. `desktop/native/motion.py` only handles Qt menu
and tooltip effects for the remaining widget dialogs.

## Weekly fixed times and reminders

Add and Edit fixed time offer "Repeats every week" and an optional Until date,
except for Setup's own blocks and sheets opened for one day. A weekly fixed
time has a `weekly-<id>` standing row beside School and Setup's activities.
Weeks show it through its inclusive Until date without cutting the stored copy.
An account holds at most 200 standing blocks at once. Setup leaves weekly fixed
times unchanged, and Copy last week's fixed times leaves them out.

Editing a weekly fixed time asks "This week only" or "This week and every week
after", except when only the repeat switch or Until changed. A change from this
week on uses the standing row, not the open week's copy. Saving a weekly fixed
time from this week on, or deleting a standing block this week and later, saves
a restore point first. The notice's Undo restores that point and also takes
back later changes. If a new repeat doubles a fixed time already made by hand
in a later week, FlexWeek names that week and removes nothing.

When no tray pop-ups can be shown, or "Leave reminders on screen" is on,
`KeptReminders` in `desktop/native/kept_alerts.py` holds a reminder as a card
with Snooze and Close. It stays until the block starts. Snooze waits five
minutes, or until the start when fewer than five minutes remain. At the start
the card goes and "starts now" takes over. Moving or deleting the block removes
its card; renaming the block renames it. The timing functions are in
`engine/engine/src/desk/remind.rs`.

## Account and setup

`qml/account/AccountFlow.qml` covers the shell until sign-in, recovery and setup
are complete. Sign in, Create account and Reset password share one card, with
Keep me signed in on this computer. At launch, a kept session stays in the Opening phase while it is checked.
A working session goes straight to the week without flashing the sign-in card. New accounts acknowledge eight
one-time recovery codes before setup.

Setup is three steps of multiple-choice cards: School hours, Study hours, and
Look & alerts. A live week preview contains only what the student entered. The
usual school days, planning style, study hours, reminder lead, preset, mode and
row size have cards. Detailed controls appear after a card that needs them, such
as Different times, sports, or a job…, Custom…, or Choose an alarm sound or
Spotify link…. The default school card is Monday to Friday, 08:00–15:00. The
last button is Open my week; setup has no first-homework or summary page.

## Drawing failure

A load, build, publish or scene-graph failure on the graphics card saves
`cpu_drawing_version` in the look file and starts one new copy with
`QT_QUICK_BACKEND=software` and `FLEXWEEK_CPU_NOTICE=1`. Unsaved edits are saved
before the old copy quits. The new copy says once, in Material's snackbar, that
it is drawing without the graphics card. That app version keeps using software
drawing at start-up; a newer version tries the graphics card again.

If software drawing fails too, the shell shows a plain page with the problem,
app version, Quit and Try again. Try again clears the saved version and starts
normally. No other interface is used as a fallback.

## Packaging and rig

A frozen build includes `desktop/native/material/tokens.json` and
`desktop/native/material/qml/` next to the executable. `theme.py` also checks
those paths when the files are not beside the source. `desktop/check_bundle.py`
reports missing Material files.

The rig finds a QML item by `objectName` or its visible words and walks visual
children, because a repeater row is not necessarily a `QObject` child. The five
screens are on the rail at desktop width and the bottom bar at phone width.
Signing out waits for unsaved changes and stays open if that save does not land.
