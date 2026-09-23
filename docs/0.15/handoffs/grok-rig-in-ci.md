# Handoff: run the real-pointer rig in CI (Grok)

The rig in `scripts/rig/` drives FlexWeek with a real pointer on a hidden desktop and checks the
week that was saved. It runs on this machine, where KWin is available. CI has no KWin. Give the rig
a second way to start a hidden X display so GitHub's Linux runner can run the same scenarios on
every pull request.

## Read first

- `scripts/rig/hidden_session.py`: starts `kwin_wayland --virtual --xwayland`, finds the new X
  display, and remembers the process by its PID.
- `scripts/rig/drive.py`: the scenarios, the pointer steps through xdotool, the assertions against
  the week reloaded from the server, and the screenshots and video it saves.
- `.github/workflows/verify.yml` for how the suite runs today.

## Build

On a branch from `feat/0.15-tabs`:

    git worktree add ~/.worktrees/flexweek-015-rigci -b grok/0-15-rig-ci feat/0.15-tabs

`feat/0.15-tabs` is at `d74f087` or later.

1. Add an Xvfb mode to `hidden_session.py`, chosen by `--server xvfb` or by KWin being absent:
   start `Xvfb` on a free display at 1400x900x24 with a small window manager on it (openbox or
   similar; `docs/0.15/plan.md` requires one, because Escape and window activation need focus to
   behave as on a desktop), wait until it takes connections, remember both PIDs the same way, and
   stop them the same way. Keep one interface for both servers, so `drive.py` needs no change
   beyond passing the choice through. The KWin path keeps `--no-global-shortcuts`.
2. A workflow job that installs what it needs (Xvfb, the window manager, xdotool, ffmpeg, the
   project's Python dependencies), runs `python scripts/rig/drive.py --design classic --tab day`
   and `--tab week`, and fails the job when any scenario fails. Month is not built yet (unit 9),
   so its three scenarios fail by design; leave them out of the job, not out of the rig.
3. Keep the artifacts: upload the run's screenshots, `results.json` and the video, so a failure can
   be looked at without a checkout.
4. Keep it under ten minutes for the classic run. Say in the pull request how long it took.

## Do not

- Do not change the scenarios, the assertions, or anything in `desktop/native/`. If a scenario
  fails in CI but passes here, that is a finding to report, not a scenario to soften.
- Do not push, open a pull request, or change the remote. Commit locally only. The workflow file
  can be committed; the owner decides when it runs on the remote.
- Do not touch `~/.worktrees/flexweek-phase5-*`.

## Prove it

1. `python scripts/rig/hidden_session.py --server xvfb start` prints a display, and the classic
   Day (7) and Week (10) scenarios pass against it on this machine with KWin stopped. They include
   zooming with the wheel: the rig's app runs with `QT_XCB_NO_XI2=1`, because Qt only hears
   xdotool's wheel through the core X protocol. Keep that.
2. The same run under `act` or a scratch container, or a clear statement of what you could not
   test locally and why.
3. `.venv/bin/python scripts/verify.py` green.

## Report back

Commit SHAs, both rig summaries (KWin and Xvfb), the run time, and anything that behaves
differently between the two displays. Claude reviews before it lands.
