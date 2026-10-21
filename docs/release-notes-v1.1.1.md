# FlexWeek 1.1.1 release notes

Paste-ready body for the v1.1.1 GitHub release. The download sections follow
`docs/github-release.md`.

```
Places homework around school and sports. Download, open a window, create an account.

**Already on 1.1.0?** You do not need to download anything. FlexWeek offers this update itself: press Update now when it asks, or open Settings (the gear) and choose Check for updates. On the phone, Settings has an Updates card. Nothing installs until you press the button.

## What changed

**An assistant on this computer** can now also change the signed-in schedule: add, edit, finish and delete homework, mark a block done, and move or delete a block. A retried request changes things once, a request made on an out-of-date week changes nothing, and school and activities still change only in the app. An assistant that should only see the schedule gets the read-only mode: it can read today, the week, the month, homework, routines and restore points, and never change anything. Reading no longer keeps you signed in for ever; only using FlexWeek, or a change the assistant makes, does.

**The Linux download carries the assistant.** The tarball and the AppImage include the helper, so an assistant starts it from the installed package. Point the assistant at `./FlexWeek-x86_64.AppImage --mcp --read-only`, or, from the tarball's FlexWeek folder, `./FlexWeek --mcp --read-only` (leave out `--read-only` to let the assistant change homework and blocks too). It talks over standard input and output, opens no network port, and uses the account kept signed in with Keep me signed in. Windows does not ship the helper.

**Fixed.** The assistant no longer creates an empty FlexWeek database when it starts before you sign in; it says "Please sign in" instead, and it picks up your account once you do. It finds FlexWeek's data where the desktop keeps it when `XDG_DATA_HOME` is set, and its changes use your local time of day, not UTC, for what has already passed.

## Known limits
- On a Mac, the assistant cannot read or change the schedule yet, and the Windows download does not include the assistant helper.
- The phone does not have Month or Day screens in this release.
- Phone sync needs the computer and the phone on the same Wi-Fi, or the public n0 relay. FlexWeek must be open on the computer.
- The Windows installer is built and checked by CI when the release is published.
```
