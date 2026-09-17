# FlexWeek 0.11.0 release notes

Paste-ready body for the v0.11.0 GitHub release. The download sections follow
`docs/github-release.md`.

```
Places homework around school and sports. Download, open a window, create an account.

This release is the polish pass after 0.10.0. You can pick how FlexWeek looks, buttons say when they are working, and the 0.10.1 hotfix is in these downloads too.

## What changed
- **Five looks in one tap.** System, Light frost, Dark frost, Nocturne and Slate. Signed-in, the choice lives on your account.
- **Customize, when you want it.** Sky, Gold, Sea or Sand, optionally on category chips. On a phone the submenu stays hidden so Motion still fits.
- **Motion Off, Normal or Extra.** Normal fades Week, Day and Month. Extra adds a short rise and pops in newly placed work. Off matches the device's reduced-motion setting. Nothing frosted is animated.
- **Buttons that are not silent.** Solve, Spread and Running late say they are working. Accepting a late start draws the new block onto the calendar.
- **One gesture to add work.** A sidebar type chip opens Add with that type already chosen.
- **Month keeps its place.** Leaving Month for Week or Day opens a date in the month you were reading.
- **From the 0.10.1 hotfix.** Running late tells you what happened, including "Nothing had to move." A nearly empty month no longer looks broken. Setup no longer names your sport for you.

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
