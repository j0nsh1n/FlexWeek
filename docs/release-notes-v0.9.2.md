# FlexWeek 0.9.2 release notes

Paste-ready body for the v0.9.2 GitHub release. The download sections follow
`docs/github-release.md`.

```
Windows installers.

## What changed
- Windows downloads are now installers instead of a zip.
  - `FlexWeek-Windows-x64-Setup.exe` installs FlexWeek for your Windows account. No administrator needed. It adds FlexWeek to the Start menu (a desktop shortcut is optional) and to Settings > Apps for uninstalling.
  - `FlexWeek-Windows-x64.msi` installs FlexWeek for every account on the PC, for schools and IT. It needs an administrator.
  - Use one installer or the other. Your weeks stay in `%APPDATA%\FlexWeek` when you uninstall or reinstall.

## What 0.9.2 fixes
- The FlexWeek shortcut in the 0.9.0 and 0.9.1 Windows zip pointed at a folder on the machine that built it, so double-clicking it did nothing useful. The installers create their shortcuts on your PC, and every release now installs each installer, opens FlexWeek through its Start menu shortcut, and uninstalls it before the files are attached.

## Download for Windows
- `FlexWeek-Windows-x64-Setup.exe`: run it, then open FlexWeek from the Start menu. If Windows shows "Windows protected your PC", choose More info, then Run anyway. FlexWeek is not code-signed yet.
- `FlexWeek-Windows-x64.msi`: every account on the PC; needs an administrator.

## Download for Linux
- `FlexWeek-Linux-x86_64.tar.gz`: extract, then open the file named FlexWeek.
- `FlexWeek-x86_64.AppImage`: one file; needs FUSE. If it won't start, run `chmod +x FlexWeek-x86_64.AppImage && ./FlexWeek-x86_64.AppImage --appimage-extract`, which unpacks a `squashfs-root` folder, then run `./squashfs-root/AppRun`. Without FUSE, the tarball is the reliable choice.

Checksums: the matching `.sha256` files. Each names only its file.
```
