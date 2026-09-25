# FlexWeek 0.15.0 release notes

Paste-ready body for the v0.15.0 GitHub release. The download sections follow
`docs/github-release.md`; the builds are made the same way as 0.14.3's.

```
Places homework around school and sports. Download, open a window, create an account.

**Already on 0.14.x?** FlexWeek offers this update itself: open Settings (the gear) and choose Check for updates.

## What changed
- **Times by the minute.** A block keeps the minute you type: 17:37 to 18:22 stays 17:37 to 18:22. Dragging moves in steps of 5 minutes, or 15 if you choose that in setup or in Settings > Planning. Homework is still planned on quarter hours, around blocks at any minute.
- **Reminders are on.** Every block reminds you before it starts, unless you turn reminders off in Settings > Alerts; accounts from before 0.15 have them turned on once. A block saved inside its reminder time reminds you at once, and a reminder shows in FlexWeek as well as in the tray.
- **A block's song plays at its start.** A block with a Spotify link plays it when the block starts. Dismiss or snooze it as you would an alarm.
- **Help and About.** More has Help, with what each screen is for and the keyboard shortcuts, and About, with the version and where your plans are saved. A tutorial and guides come later.
- **More says what each thing does.** Hover over anything under More, the plan button or the plan review to see what it does. A greyed item says why, and Unfinished works in every design.
- **It asks before you lose something.** Log out, Delete account and deleting a block each ask first. A deleted block comes back with Undo on the notice under the hours.
- **The block editor reads as a student would say it.** It is New event or Edit event, says that ticking more days repeats it this week, and names the day you missed. Save is the one filled button, and Delete is quiet at the bottom left.
- **Settings in the order you look.** Appearance & layout starts with the design and says what one is. Alerts puts reminders first, with their switch on top. Focus says "Long break after 4 focus sessions", and This computer has Manage account on a row of its own.
- **Every design drags the same way.** Day and Week in all seven designs, and both My day screens, move a block with the pointer in the step you chose, with its new times beside it while you hold it. Drag an end to make it longer or shorter, or drag across empty time to add something. If it cannot go there, it says why before you let go, and nothing moves. Escape puts it back.
- **Undo after a drag.** Moving, resizing or making a block says what changed once it is saved, under the hours, with Undo beside it: "Moved History essay to Fri 18:00." Everything under More > Advanced says what it did too.
- **Each design has its own live Day and Week.** Timeline is a ruled notebook page, and its Week reads down the page a day at a time. Mission control reads the day left to right. Bento's hero tile becomes the day. Retro desktop has Schedule.exe and Week.exe. Clay deck fans the week out as seven cards. Homework without a time waits in each design's own tray, ready to drag in.
- **The whole day, 00:00 to 24:00.** Hours scroll instead of squeezing onto the screen. Zoom with Ctrl and the mouse wheel, Ctrl with =, - or 0 wherever the keyboard is, or the two buttons by the hours; each view remembers how close it was on this computer. Every Day and Week opens at the time now, or at the first block of the day or week shown.
- **Month shows your blocks.** Every date lists what is on it with its time ("09:00 History essay"), homework due that day first. Drag one to another date to move it there at the same time. One day of something that repeats moves alone, and a date past the homework's due date says no before you let go.
- **Plan inside the hours you choose.** Setup asks when FlexWeek may plan homework, and Settings can change it. Until you choose, the whole day is open, and night is used only when the rest of the day is full. Placing something yourself works at any hour.
- **Due time is optional.** Homework is due on a date; tick "At a set time" only when it is due at a time that day, such as a 09:00 lesson. New homework starts due today.
- **Plan leaves the past alone, and can be undone.** Plan and Replan place homework only in time still to come. One Undo takes back everything a plan placed, and Redo puts it back.
- **Undo across weeks.** Moving a block to another week is one step to undo, and it never throws away later changes to that week.

## Fixed
- A block saved inside its own reminder time, such as one at 18:45 saved at 18:38 with a 10-minute reminder, now reminds you at once instead of never.
- Sign in and create account say what went wrong: an empty field, a password too short to be right, a username taken, or FlexWeek not reaching its server.
- Scrolling down Settings no longer changes every number box and dropdown the pointer passes over.
- One word for one thing: "in 20 min" everywhere, "Finished" for finished work, and "Not placed yet" for homework without a time.
- Cancelling Running late takes its preview off the screen.
- Play beside the alert sound says what to check when no sound comes out, instead of "No sound card".
- Retro desktop's Teal, Plum and Slate desktops no longer put white text on grey in Settings and the editors.
- Settings says FlexWeek 0.15.0, not 0.14.3.
- FlexWeek no longer crashes as it quits after a homework, Settings, Account or paste-preview window was opened.
- A block that cannot go where you hold it is always red, never your accent colour, in every design and look.
- Block text is never cut in half, keeps its name in sight on long blocks, and stays one size down the day.
- The planner no longer puts homework at midnight when an evening hour is free.
- Saving a week no longer fails when finished work ends at midnight.
- New homework is due today, not on the week's Monday. A length under 15 minutes or over 24 hours is refused with a reason, and the due date's calendar shows its whole month.
- Mission control opens at the time now, not at midnight.
- A homework chip shortens its title and keeps its length whole: "Science pos… · 1 h 30 min", not "Science poster · 1 h …".
- The top bar keeps whole words at every window width; where there is no room, Plan my homework says Plan.
- A short block on hours that run across shows its first letter instead of lines of "…", and the hour labels at either edge stay whole.
- "Next: … (in 23 min)" counts down with the clock.
- Hours no longer jump back to the morning after a save.
- A block made by dragging has no category until you choose one, so it no longer counts as School.
- Retro desktop's deadlines.txt keeps each date on the page at large text, and homework with no time shows once.
- Today's app's "Needs a time" bar no longer blinks empty each time the week saves.

## Download for Windows
`FlexWeek-Windows-x64-Setup.exe`

Run it to install FlexWeek for your Windows account (no administrator needed), then open FlexWeek from the Start menu. If Windows shows "Windows protected your PC", choose More info, then Run anyway. FlexWeek is not code-signed yet. Unicode text support (ICU) is part of Windows 10 version 1809 and later.

Schools and IT: `FlexWeek-Windows-x64.msi` installs FlexWeek for every account on the PC and needs an administrator. Use one installer or the other.

## Download for Linux
`FlexWeek-Linux-x86_64.tar.gz`

Extract, then open the file named FlexWeek. Needs a 64-bit Linux desktop (GNOME, KDE Plasma, Cinnamon, Xfce), glibc 2.38 or newer (Ubuntu 24.04, Linux Mint 22, Debian 13, Fedora 39 or newer), and working graphics (OpenGL or EGL). It uses libraries every desktop has, starting with libEGL.so.1; the README's "Linux libraries" lists them and shows how to find one that is missing. The X11 helpers many desktops leave out (libxcb-cursor and five others) are inside this download. Alarm sounds use your desktop's audio (PulseAudio or PipeWire); without it the alarm still appears, silently.

`FlexWeek-x86_64.AppImage` is the same app in one file. If it won't start (missing FUSE), run `chmod +x FlexWeek-x86_64.AppImage && ./FlexWeek-x86_64.AppImage --appimage-extract`, which unpacks a `squashfs-root` folder, then run `./squashfs-root/AppRun`. Without FUSE, the tarball above is the reliable choice.

## Chromebooks
Not supported. FlexWeek is a Windows and Linux desktop app, and there is no web version.

## Checksums
Optional. `FlexWeek-Windows-x64-Setup.exe.sha256`, `FlexWeek-Windows-x64.msi.sha256`, `FlexWeek-Linux-x86_64.tar.gz.sha256` and `FlexWeek-x86_64.AppImage.sha256` on this page. Each names only its file, so `sha256sum -c` works in the folder you downloaded to.

## First open
The first screen is Sign in. Choose "New here? Create an account" under it. Setup then goes a page at a time: a style, your week, how homework gets a time, reminders and the alarm sound, and your first homework. You can skip any page.
```
