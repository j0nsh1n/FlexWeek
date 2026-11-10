# GitHub release body

Paste this into `gh release create` (or the GitHub Release form). Rename nothing
in the ## Downloads list: those filenames are the ones the README links at
`/releases/latest/download/`.

Checksum files are listed after the downloads on purpose.

```
Places homework around school and sports. Download, open a window, create an account.

## Download for Windows
`FlexWeek-Windows-x64-Setup.exe`

Run it to install FlexWeek for your Windows account (no administrator needed), then open FlexWeek from the Start menu. If Windows shows "Windows protected your PC", choose More info, then Run anyway. FlexWeek is not code-signed yet. Unicode text support (ICU) is part of Windows 10 version 1809 and later.

Schools and IT: `FlexWeek-Windows-x64.msi` installs FlexWeek for every account on the PC and needs an administrator. Use one installer or the other.

## Download for Linux
`FlexWeek-Linux-x86_64.tar.gz`

Extract, then open the file named FlexWeek. Needs a 64-bit Linux desktop (GNOME, KDE Plasma, Cinnamon, Xfce), glibc 2.38 or newer (Ubuntu 24.04, Linux Mint 22, Debian 13, Fedora 39 or newer), and working graphics (OpenGL or EGL). The X11 cursor helper (libxcb-cursor) is inside this download.

`FlexWeek-x86_64.AppImage` is the same app in one file. If it won't start (missing FUSE), run `chmod +x FlexWeek-x86_64.AppImage && ./FlexWeek-x86_64.AppImage --appimage-extract`, which unpacks a `squashfs-root` folder, then run `./squashfs-root/AppRun`. Without FUSE, the tarball above is the reliable choice.

## Download for Android
`FlexWeek-Android-<version>.apk`

Open it on the phone and allow installs from your browser or file manager when Android asks. The app is signed with FlexWeek's own key, not Google Play's. Then pair it with the computer in Settings > This computer > Devices. A phone that already has FlexWeek is offered the update by the app itself.

## Chromebooks
Not supported. FlexWeek is a Windows and Linux desktop app, and there is no longer a web version to open in a browser.

## Checksums
Optional. `FlexWeek-Windows-x64-Setup.exe.sha256`, `FlexWeek-Windows-x64.msi.sha256`, `FlexWeek-Linux-x86_64.tar.gz.sha256`, `FlexWeek-x86_64.AppImage.sha256` and `FlexWeek-Android-<version>.apk.sha256` on this page. Each names only its file, so `sha256sum -c` works in the folder you downloaded to.

## First open
The first screen is Sign in. Choose "New here? Create an account" under it. Setup then goes a page at a time: a style, your week, how homework gets a time, reminders and the alarm sound, and your first homework. You can skip any page.
```

## Release checklist

The steps for a release, in order. The block above is the release body only.

Before the tag

1. Merge the fixes planned for the release. Every pull request has green checks.
2. Run "Release packages" by hand on main with no tag. It builds and tests every
   package and uploads nothing. Both jobs must pass. If anyone can try the Windows
   installers from the run's artifacts on a real PC, do; otherwise say in the notes
   that they were not tried.
3. Open a developer build for an hour (`scripts/dev-release.sh`) and note its memory
   use. Decide whether to fix, name it under Known limits, or close it.
4. Open the release pull request: `desktop/native/version.py` VERSION, the CHANGELOG
   heading `## [X.Y.Z] - <date>` over a new empty `## [Unreleased]`, Android
   `versionName` and `versionCode` (up by one), `docs/release-notes-vX.Y.Z.md`,
   `context.md`, `roadmap.md` and `README.md` up to date. Comment `@coderabbitai review`.
   Run Verify by hand on the branch so every mutation shard runs. Merge when the
   reviewer passes and every check is green.
5. Use a developer build of the merged main, and try every visible control once in
   Material and in Today's app. What turns up becomes fixes before the tag.

Cutting the release

6. Tag the merged commit `vX.Y.Z` and push the tag. The tag must equal VERSION:
   `python scripts/check_release_tag.py --tag vX.Y.Z` says so, and the packaging
   workflow runs the same check first and stops when they differ.
7. Create the GitHub release for `vX.Y.Z` as a draft, titled "FlexWeek X.Y.Z", with
   the body above and the release notes. Not a pre-release.
8. Run "Release packages" by hand with the tag. It builds from the tag, smoke-tests
   each package and the packaged assistant helper, and uploads eight files:
   `FlexWeek-Windows-x64-Setup.exe`, `FlexWeek-Windows-x64.msi`,
   `FlexWeek-Linux-x86_64.tar.gz`, `FlexWeek-x86_64.AppImage` and a `.sha256` for each.
9. Android, on the machine that holds the key: from `android/`, run
   `./gradlew testDebugUnitTest`, then the release build. Sign it with
   `scripts/android/sign-release.sh` and the key in `~/.config/flexweek-android/`.
   Name it `FlexWeek-Android-X.Y.Z.apk`, write `FlexWeek-Android-X.Y.Z.apk.sha256`
   naming only that file, and upload both. `apksigner verify --print-certs` must show
   the same certificate as the previous release's APK.
10. Check all ten files are on the draft and every checksum matches: download each and
    run `sha256sum -c`.
11. Publish as latest. Publishing starts "Release packages" again; its upload steps skip
    every file already on the release, so the checked files stay as they are. Cancel
    that run if you do not need it. To replace a file on purpose, delete it from the
    release first.
12. After publishing, check that `/releases/latest` returns the new tag; a previous
    tarball install and a developer-build install are each offered it; the phone on the
    previous version is offered and installs the new APK, then pairs and syncs both
    ways; and the `dev` pre-release is still there and not marked latest.
13. Housekeeping: list the branches, worktrees and local files that belong to releases
    older than the previous one, with sizes, and delete them after approval.
