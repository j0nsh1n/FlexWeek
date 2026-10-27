# FlexWeek 1.2.0 release notes

Places homework around school and sports. Download, open a window, create an account.

Already using FlexWeek? Choose Check for updates in Settings, or use Update now
when the app offers it. Your account, schedule, saved looks, and paired devices
stay in place.

## What changed

- A quieter planner. Add is the main top-bar action, Plan uses accent text,
  and the rail separates its sections with type and spacing.
- More calendar space. The repeated Next and overdue strip is gone.
  Overdue homework remains under More > Unfinished.
- Week as a list is under More. Ctrl+Shift+L opens it, and Escape returns
  focus to the control you were using without moving the calendar.
- The phone sync indicator is in the top bar beside More and Settings.
- Settings no longer blurs its content into a strip above Done.
- At 1024 x 640 with Large text, long Unfinished rows put their buttons
  below the words so the actions remain readable.
- Calendar refreshes keep your keyboard position while another window is active.

The Linux downloads still include the assistant helper. Start it with
`./FlexWeek-x86_64.AppImage --mcp --read-only`, or `./FlexWeek --mcp --read-only`
from the extracted tarball. This release does not change the helper's tools.

## Known limits

- Windows and Android do not include the assistant helper.
- The Android app does not have Month or Day screens.
- Sync uses the same Wi-Fi network or the public n0 relay and needs FlexWeek
  open on the computer.
