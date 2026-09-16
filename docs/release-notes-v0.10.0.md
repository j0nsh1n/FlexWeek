# FlexWeek 0.10.0 release notes

Paste-ready body for the v0.10.0 GitHub release. The download sections follow
`docs/github-release.md`.

```
Places homework around school and sports. Download, open a window, create an account.

This release adds the seven-stage student experience: exact homework deadlines, a Day agenda, reusable routines and restore points, plans that adapt when you run late, comfortable settings, account recovery and transfer, and a Month calendar.

## What changed
- **Homework with real deadlines.** Enter a due date and time, split work across weeks, keep progress when a session ends, and undo mistakes.
- **A Day agenda.** See what is due tomorrow, what is planned today, and one clear next action. Day is the default on phones; Week stays one control away.
- **Reuse and recovery.** Copy a day, apply a weekly routine, carry unfinished homework forward, and restore a week you did not mean to change.
- **Plans that adapt.** Running late previews a 15, 30 or 60 minute delay before you accept it. Spread a project across the days before it is due. Protect downtime, meals and commutes so not every gap becomes homework.
- **Comfortable settings.** Grouped settings, timer presets with a preview of how a session splits, alert volume, and a remembered layout.
- **Your account is yours.** Eight one-time recovery codes at sign-up, password recovery without email, password change, account deletion, and a previewed transfer of everything to another account.
- **A Month calendar.** Scan a month for deadlines, projects and overdue work, see planned and finished study time, and click a date to open that day.

## Download for Windows
`FlexWeek-Windows-x64-Setup.exe`

Run it to install FlexWeek for your Windows account (no administrator needed), then open FlexWeek from the Start menu. If Windows shows "Windows protected your PC", choose More info, then Run anyway. FlexWeek is not code-signed yet. Unicode text support (ICU) is part of Windows 10 version 1809 and later.

Schools and IT: `FlexWeek-Windows-x64.msi` installs FlexWeek for every account on the PC and needs an administrator. Use one installer or the other.

## Download for Linux
`FlexWeek-Linux-x86_64.tar.gz`

Extract, then open the file named FlexWeek. Needs a 64-bit Linux desktop (GNOME, KDE Plasma, Cinnamon, Xfce), glibc 2.38 or newer (Ubuntu 24.04, Linux Mint 22, Debian 13, Fedora 39 or newer), and working graphics (OpenGL or EGL). The X11 cursor helper (libxcb-cursor) is inside this download.

`FlexWeek-x86_64.AppImage` is the same app in one file. If it won't start (missing FUSE), run `chmod +x FlexWeek-x86_64.AppImage && ./FlexWeek-x86_64.AppImage --appimage-extract`, which unpacks a `squashfs-root` folder, then run `./squashfs-root/AppRun`. Without FUSE, the tarball above is the reliable choice.

## Chromebooks
A hosted web version is not online yet. From the source tree: `uvicorn backend.app:app --reload` then open http://127.0.0.1:8000.

## Checksums
Optional. `FlexWeek-Windows-x64-Setup.exe.sha256`, `FlexWeek-Windows-x64.msi.sha256`, `FlexWeek-Linux-x86_64.tar.gz.sha256` and `FlexWeek-x86_64.AppImage.sha256` on this page. Each names only its file, so `sha256sum -c` works in the folder you downloaded to.

## First open
Choose Create account. A short setup asks for school hours, a sport, and the first homework, then runs Solve. You can skip any step.

## Trying it out
This is the first release of the student experience and it has not been through student trials yet. Your weeks stay on your own computer. Problems and confusing wording are worth reporting in the issue tracker.
```
