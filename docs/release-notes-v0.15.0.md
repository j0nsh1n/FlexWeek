# FlexWeek 0.15.0 release notes (draft)

Paste-ready body for the v0.15.0 GitHub release, drafted before review. The download sections follow
`docs/github-release.md` and are copied from 0.14.3 unchanged; check them against the build.

```
Places homework around school and sports. Download, open a window, create an account.

**Already on 0.14.x?** FlexWeek offers this update itself: open Settings (the gear) and choose Check for updates.

## What changed
- **Every design drags the same way.** Day and Week in all seven designs, and both My day screens, move a block with the pointer a quarter hour at a time, with its new times beside it while you hold it. Drag an end to make it longer or shorter, or drag across empty time to add something. If it cannot go there, it says why before you let go, and nothing moves. Escape puts it back.
- **Each design has its own live Day and Week.** Timeline is a ruled notebook page, and its Week reads down the page a day at a time. Mission control reads the day left to right. Bento's hero tile becomes the day. Retro desktop has Schedule.exe and Week.exe. Clay deck fans the week out as seven cards. Homework without a time waits in each design's own tray, ready to drag in.
- **The whole day, 00:00 to 24:00.** Hours scroll instead of squeezing onto the screen. Zoom with Ctrl and the mouse wheel, Ctrl with =, - or 0, or the two buttons by the hours; each view remembers how close it was on this computer.
- **Month shows your blocks.** Every date lists what is on it with its time ("09:00 History essay"), homework due that day first. Drag one to another date to move it there at the same time. One day of something that repeats moves alone, and a date past the homework's due date says no before you let go.
- **Plan inside the hours you choose.** Setup asks when FlexWeek may plan homework, and Settings can change it. Until you choose, the whole day is open, and night is used only when the rest of the day is full. Placing something yourself works at any hour.
- **Due time is optional.** Homework is due on a date; tick "At a set time" only when it is due at a time that day, such as a 09:00 lesson.
- **Undo across weeks.** Moving a block to another week is one step to undo, and it never throws away later changes to that week.

## Fixed
- FlexWeek no longer crashes as it quits after a homework, Settings, Account or paste-preview window was opened.
- A block that cannot go where you hold it is always red, never your accent colour, in every design and look.
- Block text is never cut in half, keeps its name in sight on long blocks, and stays one size down the day.
- The planner no longer puts homework at midnight when an evening hour is free.
- Saving a week no longer fails when finished work ends at midnight.

## Download for Windows
`FlexWeek-Windows-x64-Setup.exe`

Run it to install FlexWeek for your Windows account (no administrator needed), then open FlexWeek from the Start menu. If Windows shows "Windows protected your PC", choose More info, then Run anyway. FlexWeek is not code-signed yet. Unicode text support (ICU) is part of Windows 10 version 1809 and later.

Schools and IT: `FlexWeek-Windows-x64.msi` installs FlexWeek for every account on the PC and needs an administrator. Use one installer or the other.

## Download for Linux
`FlexWeek-Linux-x86_64.tar.gz`

Extract, then open the file named FlexWeek. Needs a 64-bit Linux desktop (GNOME, KDE Plasma, Cinnamon, Xfce), glibc 2.38 or newer (Ubuntu 24.04, Linux Mint 22, Debian 13, Fedora 39 or newer), and working graphics (OpenGL or EGL). The X11 cursor helper (libxcb-cursor) is inside this download. Alarm sounds use your desktop's audio (PulseAudio or PipeWire); without it the alarm still appears, silently.

`FlexWeek-x86_64.AppImage` is the same app in one file. If it won't start (missing FUSE), run `chmod +x FlexWeek-x86_64.AppImage && ./FlexWeek-x86_64.AppImage --appimage-extract`, which unpacks a `squashfs-root` folder, then run `./squashfs-root/AppRun`. Without FUSE, the tarball above is the reliable choice.

## Chromebooks
Not supported. FlexWeek is a Windows and Linux desktop app, and there is no web version.

## Checksums
Optional. `FlexWeek-Windows-x64-Setup.exe.sha256`, `FlexWeek-Windows-x64.msi.sha256`, `FlexWeek-Linux-x86_64.tar.gz.sha256` and `FlexWeek-x86_64.AppImage.sha256` on this page. Each names only its file, so `sha256sum -c` works in the folder you downloaded to.

## First open
The first screen is Sign in. Choose "New here? Create an account" under it. Setup then goes a page at a time: a style, your week, how homework gets a time, reminders and the alarm sound, and your first homework. You can skip any page.
```
