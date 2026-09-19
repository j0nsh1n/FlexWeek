# FlexWeek 0.12.0 release notes

Paste-ready body for the v0.12.0 GitHub release. The download sections follow
`docs/github-release.md`.

```
Places homework around school and sports. Download, open a window, create an account.

This release replaces the Chromium desktop window with native Qt widgets. You can pick a look, pick a layout, and the downloads are that native app.

## What changed
- **Native desktop.** The Windows and Linux downloads are Qt widgets talking to the same local planner. No Chromium in the package.
- **Looks.** Settings Look lists System, Light frost, Dark frost, Nocturne and Slate, then Terminal, Poster, Ink, High contrast, Paper and Pastel. Customize still has Surface, Corners, Depth, Font, Calendar blocks and Density. Knobs you set by hand stay when you change Look. Those presets stay on this computer.
- **Layouts, native only.** Layout picks how you see the week: Today's app, Timeline, Mission control, Bento, Retro desktop or Clay deck, and a day screen of One thing or Day dial. My day, or T, opens the day screen. A design of its own gets the window; planning controls including Copy, Paste and Duplicate live under Tools.
- **Drafts and reminders.** An unsaved week stays as a draft when you open another week. Reminders for today still fire if you are looking at another week.

Looks and layouts do not yet sync to your account. The web client has the looks, not the layouts.

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
```
