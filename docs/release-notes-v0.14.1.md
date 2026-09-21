# FlexWeek 0.14.1 release notes

Paste-ready body for the v0.14.1 GitHub release. The download sections follow
`docs/github-release.md`.

```
Places homework around school and sports. Download, open a window, create an account.

**Already on 0.14.0?** You do not need to download anything. FlexWeek offers this update itself: press Update now when it asks, or open Settings (the gear) and choose Check for updates.

## What changed
- **One place for each thing.** Plan my homework, More and a new Settings gear sit in the top bar in every design, including My day. Designs no longer swap More for a Tools button or hide Plan my homework.
- **More is for doing, Settings is for choosing.** More holds Adding, Planning, Advanced (undo, copy and paste, save, restore, reload) and Log out. Look, layout, Account, Availability and Check for updates are in Settings, and look and layout share one page.
- **Settings saves as you go.** There is no OK or Cancel. A change shows straight away and is saved a moment later, and Close keeps everything. Account and Availability still have their own Save.
- **Time, not session counts.** A day says "1 h planned · 0 done", and spreading homework says "3 h ready to add before Sun 23:59."
- **Running late says what happened:** why it cannot run yet, or which time is now locked and whether anything moved.

## Fixed
- Typing a sport name in the first-week setup could give "SoccSoccer". The field is now empty with an example in it, and a time is selected when you click into it, so typing replaces it.
- Settings cut off its dropdown arrows, its descriptions and the alert Test button, and at large text the names of its own pages.
- The Running late notice broke one-line messages in two and covered the view buttons at large text.

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
The first screen is Sign in. Choose "New here? Create an account" under it. A short setup asks for school hours, a sport, and the first homework, then runs Solve. You can skip any step.
```
