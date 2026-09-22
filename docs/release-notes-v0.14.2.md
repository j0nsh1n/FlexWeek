# FlexWeek 0.14.2 release notes

Paste-ready body for the v0.14.2 GitHub release. The download sections follow
`docs/github-release.md`.

```
Places homework around school and sports. Download, open a window, create an account.

**Already on 0.14.0 or 0.14.1?** FlexWeek offers this update itself: open Settings (the gear) and choose Check for updates. If it stays on "Checking for updates…", download the file for your computer below instead. That hang is one of the things this release fixes.

## What changed
- **Your plan stays put.** Plan my homework saves the times it chooses, so they are still on the calendar after a restart or signing in again. Finishing one homework, undoing, or adding an event leaves the rest where it was. A new commitment over planned homework takes only that homework's time, names it, says why, and offers Find a new time.
- **Plan and Replan.** Plan my homework keeps the times that already work and places only what needs one. Replan all my homework, under More and in the plan review, plans everything again.
- **Every screen tells the truth about today.** Homework due today that has no time yet is named in every design and on both day screens, instead of the day being called free. Day and Month count only homework that has a time as planned.
- **Keep me signed in.** A box on the sign-in card, on by default, opens your week at the next launch. Log out forgets it, for a shared computer.
- **School hours** is under More, for when you skipped school during setup.
- **Reasons you can read.** When homework cannot get a time, FlexWeek says what stopped it, such as "Your fixed plans and finished work leave no gap long enough for it before it is due." Deadlines are tagged Plenty of time, Tight, or Cutting it close.
- **Settings shows what applies.** Look, Accent, Surface, Corners and Blocks appear only for the views they change.
- Smaller things: Today sits beside the week arrows. Fixed activities are a Start and an End. The view menus say what each view is for (Calendar, Agenda, Dashboard). Creating an account shows the username rule, and the password can be shown. Optional homework fields sit behind More details.

## Fixed
- Check for updates could stay on "Checking for updates…" for good when GitHub limited checks from a shared school or phone network. It now finds the update another way, gives up after 15 seconds of silence, and says so when it cannot check.
- Settings and the homework editor could be squeezed to about 150 pixels tall.
- The first-week setup covered the sport and homework fields with its buttons.
- After a missed day, the new times were lost on restart.
- Month showed parts of the week view in some designs.

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
