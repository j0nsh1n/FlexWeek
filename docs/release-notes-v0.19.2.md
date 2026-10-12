# FlexWeek 0.19.2 release notes

Paste-ready body for the v0.19.2 GitHub release. The download sections follow
`docs/github-release.md` and are copied from 0.19.1 unchanged.

```
Places homework around school and sports. Download, open a window, create an account.

**Already on 0.19.1 or 0.19.0?** You do not need to download anything. FlexWeek offers this update itself: press Update now when it asks, or open Settings (the gear) and choose Check for updates.

## What changed
- **Typing an end time.** On the 12-hour clock, an end typed without AM or PM is read as the one after its start: School from 8:30 AM to "3:15" ends at 3:15 PM. An end before its start is said right under End, and Setup and School hours offer the other half ("Did you mean 3:15 PM?").
- **Skip in Setup keeps what you typed.** It asks before dropping a changed School or activity, Esc never throws anything away, and a skipped step is marked Skipped.
- **Plan never loses homework time.** Work due within a week is never cut up, later work gets a fair share of the days you can still study, "In one go" homework stays whole, and what doesn't fit waits in Not placed yet and moves into the next week you plan. The plan message, Not placed yet and More all count the same time.
- **More counts what still needs a time.** A small count on More matches Not placed yet, and More > Unfinished opens that list. The bar that used to appear above the week, and move it, is gone.
- **Undo after Plan stays long enough.** It waits while your pointer is on it, pauses while FlexWeek is in the background, shows the seconds left, and is the first Tab stop after the week. Replan gets Undo too.
- **Running late's preview reads cleanly:** each change once, with its name, day and both times; the count shows once, and the buttons line up.
- **Running late moves the right thing.** A block already under way moves by your delay and keeps its length, nothing moves to a time already past, and the preview shows the day and both times.
- **Deleting a repeating block** asks once and names the days ("Delete Soccer on every Tue and Thu this week?"), with This day only, This week only and This week and later for School and activities.
- **Problems show under the field** that has them, push the form down instead of covering it, and never move your cursor while you type.
- **Tabbing through the week no longer makes it jump.** The keyboard list of the week's blocks opens from a fixed "Week as a list · Ctrl+Shift+L" row, over the week.
- **Question boxes fit their words.** Skip this step and Delete a block show every button in full and stack them when there is no room; "Fix them" puts the keyboard back on the time to fix. A time problem sits on its own line under the row instead of stretching the box.
- **Enter submits the sign-in forms,** and the keyboard goes to the first problem. Not placed yet shows each part of a split homework with its own time. The due date steps a day with Up and Down and a week with Page Up and Page Down.
- **The "Week as a list" row shows its words whole** in every look and text size.
- **Easier to see and reach:** chip edges, the off switch and Retro's focused fields; Light, Dark and System by Tab while a More look is worn; Setup's activity choice read out by name; "9 AM–12 AM" keeps both marks.
- **Sign in keeps your text size and High contrast** from your last session on this computer.
- **Safer files:** a week, backup or restore point with two blocks sharing one id is refused with a message, and the recovery codes are cleared once you continue to your week.

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
