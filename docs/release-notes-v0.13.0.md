# FlexWeek 0.13.0 release notes

Paste-ready body for the v0.13.0 GitHub release. The download sections follow
`docs/github-release.md`.

```
Places homework around school and sports. Download, open a window, create an account.

This release makes the alarms ring. FlexWeek had six alarm sounds, a volume slider and no audio in it at all, so every alarm was a silent box on the screen. It also finishes the other controls that saved a setting and changed nothing, and drops the browser version: FlexWeek is the desktop app now.

## What changed
- **Alarms make a sound.** Five tones, a Test button beside the volume, and days you pick per alarm. An alarm set to Spotify opens its track and falls back to a chime if that does not open. A computer with no sound card shows the alarm without a sound instead of failing.
- **Split long homework into focus sessions** works on the desktop. Plan reserves room for the breaks, then lays out your focus chunks and breaks on the day it chose.
- **Settings that did nothing now do it.** Start FlexWeek when I log in, Open on Day, Colour chips with my accent, Keep alerts visible until handled, and the end-of-session chime.
- **One look everywhere.** The design you pick in Layout now dresses Day and Month too, not only the week.
- **Signing in is the sign-in screen.** Creating an account is a line under it rather than an equal button.
- **Plan says what it did.** After Solve, a panel lists what moved and why, in the solver's own words.

## No browser version
The web version is gone. Earlier releases shipped a browser client next to the app, kept in step by hand, and most of the half-finished parts of the app were the desktop side of that pairing. There is one FlexWeek now and it is this download. Weeks exported from an older browser build still import.

## Download for Windows
`FlexWeek-Windows-x64-Setup.exe`

Run it to install FlexWeek for your Windows account (no administrator needed), then open FlexWeek from the Start menu. If Windows shows "Windows protected your PC", choose More info, then Run anyway. FlexWeek is not code-signed yet. Unicode text support (ICU) is part of Windows 10 version 1809 and later.

Schools and IT: `FlexWeek-Windows-x64.msi` installs FlexWeek for every account on the PC and needs an administrator. Use one installer or the other.

## Download for Linux
`FlexWeek-Linux-x86_64.tar.gz`

Extract, then open the file named FlexWeek. Needs a 64-bit Linux desktop (GNOME, KDE Plasma, Cinnamon, Xfce), glibc 2.38 or newer (Ubuntu 24.04, Linux Mint 22, Debian 13, Fedora 39 or newer), and working graphics (OpenGL or EGL). The X11 cursor helper (libxcb-cursor) is inside this download. Alarm sounds use your desktop's audio (PulseAudio or PipeWire); without it the alarm still appears, silently.

`FlexWeek-x86_64.AppImage` is the same app in one file. If it won't start (missing FUSE), run `chmod +x FlexWeek-x86_64.AppImage && ./FlexWeek-x86_64.AppImage --appimage-extract`, which unpacks a `squashfs-root` folder, then run `./squashfs-root/AppRun`. Without FUSE, the tarball above is the reliable choice.

## Chromebooks
Not supported. FlexWeek is a Windows and Linux desktop app, and there is no longer a web version to open in a browser.

## Checksums
Optional. `FlexWeek-Windows-x64-Setup.exe.sha256`, `FlexWeek-Windows-x64.msi.sha256`, `FlexWeek-Linux-x86_64.tar.gz.sha256` and `FlexWeek-x86_64.AppImage.sha256` on this page. Each names only its file, so `sha256sum -c` works in the folder you downloaded to.

## First open
The first screen is Sign in. Choose "New here? Create an account" under it. A short setup asks for school hours, a sport, and the first homework, then runs Solve. You can skip any step.
```
