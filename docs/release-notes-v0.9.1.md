# FlexWeek 0.9.1 release notes

Paste-ready body for the v0.9.1 GitHub release. The download sections follow
`docs/github-release.md`.

```
A fix release for 0.9.0.

## What broke in 0.9.0
- After first-week setup, "Add to my week and Solve" could turn the window blank white, with no week, no message and no way back.
- The AppImage checksum file held the build machine's folder path, so `sha256sum -c` failed next to the download.
- The Windows notes still said to open FlexWeek.exe, which now sits inside `app/`.

## What 0.9.1 fixes
- If FlexWeek's page stops, the window reopens it by itself, with solid panels instead of frosted glass, and runs Solve again, so your placed homework and What Solve did come back. Your week was already saved. If it stops again right away, FlexWeek shows a Reload button instead of a blank window.
- Every download is now checked before it is attached: the packaged app creates a test account, goes through setup to "Add to my week and Solve", and must show the week on screen, not a blank window.
- `FlexWeek-x86_64.AppImage.sha256` names only the file.
- If the AppImage won't start (missing FUSE), run `chmod +x FlexWeek-x86_64.AppImage && ./FlexWeek-x86_64.AppImage --appimage-extract`, which unpacks a `squashfs-root` folder, then run `./squashfs-root/AppRun`. Without FUSE, the tarball is the reliable choice.
- Windows: double-click FlexWeek (the shortcut), not files inside app/.

If you saw the blank window in 0.9.0, please try 0.9.1 and tell us your system (Windows or Linux, which download, and whether it runs in a virtual machine).

## Downloads
- `FlexWeek-Windows-x64.zip` — extract, then double-click FlexWeek (the shortcut).
- `FlexWeek-Linux-x86_64.tar.gz` — extract, then open the file named FlexWeek.
- `FlexWeek-x86_64.AppImage` — one file; needs FUSE, or use the extract step above.
- Checksums: the matching `.sha256` files. Each names only its file.
```
