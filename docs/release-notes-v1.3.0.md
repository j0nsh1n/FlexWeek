# FlexWeek 1.3.0 release notes

Places homework around school and sports. Download, open a window, create an account.

Already using FlexWeek? Choose Check for updates in Settings, or use Update now
when the app offers it. Your account, schedule, saved looks, and paired devices
stay in place.

## What changed

- A new look: Material 3. It is one more style in Settings > Look, beside the
  ones you know, and Today's app is still the default. Choosing it opens a
  Material window with Day, Week, Month, My day, Focus and Settings, and
  choosing another look swaps back with no restart. You can pick a colour for
  it and light or dark.
- Settings > Look shows a live preview of your week as you change a style or
  its options.
- Planner settings. Keep weekends homework-free, leave a 15 or 30 minute gap
  between tasks, put urgent deadlines first, and split a long task. Homework now
  uses free days before the due date instead of piling up on the last one.
  Settings you have not changed leave your week where it is.
- Place now puts a homework at the first free time that fits all of it, and the
  message tells you where it went.
- Ctrl+Z undoes your last change in Material, and Ctrl+Shift+Z or Ctrl+Y does
  it again.
- Week and Day show blocks that share time overlapped, so a homework pinned over
  Soccer still shows and opens. Click or drag over empty time to add homework or
  fixed time right there.
- Focus fills the window with the phase, the task and the timer, and plays Rain,
  Lo-Fi or White noise while you work.
- The assistant helper can plan a day (Plan my homework for a day or a week),
  add and change breaks and events, and take a day off a block. Each change
  saves a restore point first, and one step brings the schedule back.
- Settings > Computer has Get developer builds, for people who want test builds
  before a release.

The assistant helper is still in the Linux downloads. Start it with
`./FlexWeek-x86_64.AppImage --mcp --read-only`, or `./FlexWeek --mcp --read-only`
from the extracted tarball. Drop `--read-only` to let it change your schedule.

## Known limits

- Windows and Android do not include the assistant helper.
- Developer builds are a Linux tarball only.
- The Android app does not have Month or Day screens.
- Material is an added style. Today's app is still the default.
- Sync uses the same Wi-Fi network or the public n0 relay and needs FlexWeek
  open on the computer.
- In Material, Ctrl+mouse-wheel zoom may not work on some Linux desktops. Use Ctrl+=
  and Ctrl+- or the zoom buttons above the hours instead.
- Material can use more memory over a long session. If FlexWeek grows slow, close
  and open it again.
