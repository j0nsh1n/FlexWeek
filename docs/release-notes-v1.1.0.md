# FlexWeek 1.1.0 release notes

Paste-ready body for the v1.1.0 GitHub release. The download sections follow
`docs/github-release.md`.

```
Places homework around school and sports. Download, open a window, create an account.

**Already on 1.0.0?** You do not need to download anything. FlexWeek offers this update itself: press Update now when it asks, or open Settings (the gear) and choose Check for updates. On the phone, Settings has an Updates card. Nothing installs until you press the button.

## What changed

**Phone.** Week, Add homework, Plan and Running late are in the released app. Running late is a slider from 5 to 60 minutes, in steps of 5. Each move says where it came from and why, and a fixed time stays put. Focus starts from Today, shows on the lock screen, and adds its minutes once when it finishes. An Up next widget shows what is now or next. The app follows the phone's dark mode. It can update itself from GitHub Releases, and it checks the download before Android's install dialog opens.

**This computer.** Dragging one day of a repeating class moves only that day. At a small window with Large text, Start focus and the Plan result keep their words, and Sign in scrolls instead of growing past the screen. After you save recovery codes, you land on today's week. Before planning overdue homework, the choices are Plan into this week, Mark as finished, and Not now.

**An assistant on this computer** can read the signed-in schedule: today, the week, the month, homework, routines and restore points. It uses FlexWeek's session file and opens no network port. On Windows it stops until it can check that the file stays private.

## Known limits
- On a Mac, that assistant cannot read the schedule yet.
- If the assistant starts before you are signed in, it keeps saying to sign in until it is started again.
- The phone does not have Month or Day screens in this release.
- Phone sync needs the computer and the phone on the same Wi-Fi, or the public n0 relay. FlexWeek must be open on the computer.
- The Windows installer is built and checked by CI when the release is published.
```
