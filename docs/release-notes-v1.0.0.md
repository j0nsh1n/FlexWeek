# FlexWeek 1.0.0 release notes

Paste-ready body for the v1.0.0 GitHub release. The download sections follow
`docs/github-release.md` and the v0.19.2 notes.

```
Places homework around school and sports. Download, open a window, create an account.

**Already on 0.19.2 or earlier?** You do not need to download anything. FlexWeek offers this update itself: press Update now when it asks, or open Settings (the gear) and choose Check for updates.

## What changed

**Phone app and sync.** An Android app (Android 8.0 or newer) shows today's agenda, reminders, pairing and background sync. Link a phone in Settings > This computer > Devices with an 8-digit code, shown as two groups of four. The code lasts 5 minutes, three wrong tries end it, and a code works once. You type the code on the phone. A status dot in the bottom strip shows that a linked phone is there. When your computer isn't on the same Wi-Fi, FlexWeek uses a public relay run by n0. It sees that two devices are talking, not what they send. With no phone linked, FlexWeek opens no network connection. The phone runs the same engine as your computer, so it shows and syncs your real homework, both ways.

**Week rail and planning.** The side of the week is a fixed Agenda: what is next (with Start focus on homework), No time yet chips to drag onto a day, and what is due this week. A strip under the bar says what is next, how many items are overdue, and Week as a list (Ctrl+Shift+L). Plan shows how many homework items still need a time. Click the week title to open a mini month. Blocks can show Overdue, Left from last week or Placed by Plan when the tag fits beside the time. Month opens on its first row, with this week banded. Click a date to fill the date pane; Open Day opens that day.

**My day.** One thing shows a ring, Later today, a Then list and day letters. Day dial is a list beside its ring. The not-placed strip shows the count only.

**Forms.** Add homework asks What, When and How long. Add fixed time asks What, When, and What category is it. Each answer shows as a crumb you can click. Edit stays one page. Forms share one look: a caption above each field, and a problem line as wide as that field. Closing a form you have changed asks "Discard what you typed?" Keep me signed in lasts 30 days; without it, 7 days. Using FlexWeek renews that length.

**Accessibility and looks.** Day, Week, Month and My day are one group, so Tab reaches it once and the arrow keys move between them. In Settings > Look, the look you are wearing shows a check badge and "Wearing", cards move with the arrow keys, and a screen reader hears the name, selected, and its place. High contrast suggests Large text. Homework outlines use the class colour, never error red. Empty days say "Nothing planned".

## Also
- More > Unfinished shows each leftover with its due date. Overdue homework that already has a time stays pressable so you can start focus. The leftover buttons read Plan into this week and Mark as finished.
- Edit homework says when it is planned and when it is due, like "Planned Fri 16 · due Wed 21".
- Before importing a backup, FlexWeek says whose weeks it adds, replaces or deletes, and which homework will be deleted.
- A past time is refused with the next quarter hour, or that the day is over.
- Running late moves blocks that already have a time and never places waiting homework.
- Study hours is the one name for availability.
- Sessions last 30 days when Keep me signed in is ticked, 7 days when it is not.
- The original green dumbbell logo is back, and the Android app uses it as its launcher icon.
- Month keeps Next and the overdue count in its strip, and Today and Add stay whole on the top bar at narrow widths and Large text.
- The three-step form's step tabs fit their words.

## Known limits
- The Windows installer is built and checked by CI when the release is published.
- Phone sync needs the computer and the phone on the same Wi-Fi, or the public n0 relay. FlexWeek must be open on the computer.
- Pairing is typed: an 8-digit code. Camera scan is not in this build.
- Running Plan on the phone and the computer before they have synced can give the same homework two times.
- Look, theme, text size and 12- or 24-hour clock stay on each device. The rest of the week syncs.
- Add homework, Plan, Running late and Week on the phone are in debug builds only.
- A restore copy of the phone-link key is later.

## Download for Windows
`FlexWeek-Windows-x64-Setup.exe`

Run it to install FlexWeek for your Windows account (no administrator needed), then open FlexWeek from the Start menu. If Windows shows "Windows protected your PC", choose More info, then Run anyway. FlexWeek is not code-signed yet. Unicode text support (ICU) is part of Windows 10 version 1809 and later.

Schools and IT: `FlexWeek-Windows-x64.msi` installs FlexWeek for every account on the PC and needs an administrator. Use one installer or the other.

## Download for Linux
`FlexWeek-Linux-x86_64.tar.gz`

Extract, then open the file named FlexWeek. Needs a 64-bit Linux desktop (GNOME, KDE Plasma, Cinnamon, Xfce), glibc 2.38 or newer (Ubuntu 24.04, Linux Mint 22, Debian 13, Fedora 39 or newer), and working graphics (OpenGL or EGL). It uses libraries every desktop has, starting with libEGL.so.1. The X11 helpers many desktops leave out (libxcb-cursor and five others) are inside this download. Alarm sounds use your desktop's audio (PulseAudio or PipeWire); without it the alarm still appears, silently.

`FlexWeek-x86_64.AppImage` is the same app in one file. If it won't start (missing FUSE), run `chmod +x FlexWeek-x86_64.AppImage && ./FlexWeek-x86_64.AppImage --appimage-extract`, which unpacks a `squashfs-root` folder, then run `./squashfs-root/AppRun`. Without FUSE, the tarball above is the reliable choice.

## Chromebooks
Not supported. FlexWeek is a Windows and Linux desktop app, and there is no web version.

## Checksums
Optional. `FlexWeek-Windows-x64-Setup.exe.sha256`, `FlexWeek-Windows-x64.msi.sha256`, `FlexWeek-Linux-x86_64.tar.gz.sha256` and `FlexWeek-x86_64.AppImage.sha256` on this page. Each names only its file, so `sha256sum -c` works in the folder you downloaded to.

## First open
The first screen is Sign in. Choose "New here? Create an account" under it. Setup then goes a page at a time: a style, your week, how homework gets a time, reminders and the alarm sound, and your first homework. You can skip any page.
```
