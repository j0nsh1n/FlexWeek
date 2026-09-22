# FlexWeek 0.14.3 release notes

Paste-ready body for the v0.14.3 GitHub release. The download sections follow
`docs/github-release.md`.

```
Places homework around school and sports. Download, open a window, create an account.

**Already on 0.14.x?** FlexWeek offers this update itself: open Settings (the gear) and choose Check for updates. On 0.14.0 or 0.14.1, if it stays on "Checking for updates…", download the file for your computer below instead.

## What changed
- **Drag it where you want it.** On the Calendar a block moves with the pointer, a quarter hour at a time and into another day, with its new times written on it. Drag its top or bottom edge to make it longer or shorter, or drag across empty time to add something there. Two things at the same time are allowed: they sit side by side, each with a dot so you notice. Dragging one day of something that repeats, like Wednesday's School, moves only that day.
- **Dragging works in every design.** Mission control, the Day dial and One thing take a drop at the time under the pointer. Timeline, Bento, Retro desktop and Clay deck open the day's hours at the side while you drag: hold the block over another day's name to switch days, then let go at a time.
- **Homework you place yourself stays put.** Drag homework onto the calendar, or use Choose a time in the homework editor. Every plan, Replan all included, leaves it where you put it. Let FlexWeek move it hands it back to the planner.
- **Setup, a page at a time.** A new account starts from a style, picked from real pictures of each design, then sets up the week (school, any number of sports, clubs and jobs, and No homework after), how homework gets a time, reminders and the alarm sound, and up to three first homework. Skip any page. Quitting halfway picks up on the same page, and Settings > This computer > Run setup again brings it back.
- **Choose how homework gets a time** in Settings > Planning: as you add it, when you press Plan my homework (the default), or by dragging it yourself.
- **Study windows for one subject.** Plans try a session in its own subject's window first.
- **Alarm sounds.** Settings > Alerts: Chime, Soft, Bright, Low, Glass, or a Spotify song or playlist. A Spotify alarm plays in your own Spotify app, whole songs, free or Premium. On Linux FlexWeek names the song and pauses Spotify when you stop or snooze the alarm. On Windows a song starts in Spotify and stops with the alarm; a playlist also rings the tone, since Spotify won't start one by itself there. Without the Spotify app, the link opens in your browser and the tone rings.
- **Every control in your design's colours:** scrollbars, dropdowns, check boxes, radio buttons, menus, tooltips and the date picker.
- **Movement that helps you follow along.** Views cross-fade and weeks slide the way you went. Settings > Appearance & layout > Animations: Normal, More movement or Off.
- Smaller things: due dates read "Sun 27 Sep 2026, 23:59". The More menu shows its headings. Changes to the week redraw faster.

## Fixed
- On a dark look under KDE, unticked boxes, radio buttons and the spin arrows could not be seen.
- A block dragged while FlexWeek was saving went back to where it was when the save finished.

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
