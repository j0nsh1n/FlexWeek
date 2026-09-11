# GitHub release body

Paste this into `gh release create` (or the GitHub Release form). Rename nothing
in the ## Downloads list: those filenames are the ones the README links at
`/releases/latest/download/`.

Checksum files are listed after the downloads on purpose.

```
Places homework around school and sports. Download, open a window, create an account.

## Download for Windows
`FlexWeek-Windows-x64.zip`

Extract the zip, then double-click FlexWeek (the shortcut), not files inside app/. If Windows shows "Windows protected your PC", choose More info, then Run anyway. FlexWeek is not code-signed yet. Unicode text support (ICU) is part of Windows 10 version 1809 and later.

## Download for Linux
`FlexWeek-Linux-x86_64.tar.gz`

Extract, then open the file named FlexWeek. Needs a 64-bit Linux desktop (GNOME, KDE Plasma, Cinnamon, Xfce), glibc 2.38 or newer (Ubuntu 24.04, Linux Mint 22, Debian 13, Fedora 39 or newer), and working graphics (OpenGL or EGL). The X11 cursor helper (libxcb-cursor) is inside this download.

`FlexWeek-x86_64.AppImage` is the same app in one file. If it won't start (missing FUSE), run `chmod +x FlexWeek-x86_64.AppImage && ./FlexWeek-x86_64.AppImage --appimage-extract`, which unpacks a `squashfs-root` folder, then run `./squashfs-root/AppRun`. Without FUSE, the tarball above is the reliable choice.

## Chromebooks
A hosted web version is not online yet. From the source tree: `uvicorn backend.app:app --reload` then open http://127.0.0.1:8000.

## Checksums
Optional. `FlexWeek-Windows-x64.zip.sha256`, `FlexWeek-Linux-x86_64.tar.gz.sha256` and `FlexWeek-x86_64.AppImage.sha256` on this page. Each names only its file, so `sha256sum -c` works in the folder you downloaded to.

## First open
Choose Create account. A short setup asks for school hours, a sport, and the first homework, then runs Solve. You can skip any step.
```
