# FlexWeek 0.14.0 release notes

Paste-ready body for the v0.14.0 GitHub release. The download sections follow
`docs/github-release.md`.

```
Places homework around school and sports. Download, open a window, create an account.

**This is the last update you download by hand.** From now on FlexWeek checks for a newer version itself, tells you what changed, and installs it when you say so. 0.13.0 shipped before that existed, which is why this one still needs a download.

## What changed
- **FlexWeek updates itself.** It looks for a newer version once a day at most, and nothing installs until you press Update now. You can skip a version or turn checking off. A download that does not match its published checksum is thrown away rather than run.
- **The week saves itself.** Save stopped being a button you have to remember. It saves a second or so after you stop changing things and retries on its own if it fails. If another window changed the same week, it still asks you rather than guessing.
- **Today's app is one row.** The week you are on is a heading instead of nothing at all, Previous and Next are arrows, Day / Week / Month is one control, and Plan my homework is the one button that stands out. Everything else moved under More.
- **Dark in every design.** Bento and Clay were light-only; they now have Midnight and Dusk. Every design has a dark option, and Match my look carries your theme into any of them.
- **Day and Month in every design.** Timeline, Mission control, Bento, Retro desktop and Clay deck draw those views in their own style instead of falling back to a plain list.

## Fixed
- **Day did nothing.** On a real week, pressing Day left the week grid on screen. It was a crash in the redraw that Qt swallowed, so the button just looked dead. This is in 0.13.0, and it is the main reason to update.
- The first-week setup card was see-through, with the calendar drawn through its own text.

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
