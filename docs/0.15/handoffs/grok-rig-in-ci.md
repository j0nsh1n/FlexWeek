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

1. Add an Xvfb mode to `hidden_session.py`, chosen by `--server xvfb` or by KWin being absent:
   start `Xvfb` on a free display at 1400x900x24, wait until it takes connections, remember the
   PID the same way, and stop it the same way. Keep one interface for both, so `drive.py` needs no
   change beyond passing the choice through.
2. A workflow job that installs what it needs (Xvfb, xdotool, the project's Python dependencies),
   runs `python scripts/rig/drive.py --design classic`, and fails the job when any scenario fails.
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

1. `python scripts/rig/hidden_session.py --server xvfb start` prints a display, and
   `python scripts/rig/drive.py --design classic` passes its Day and Week scenarios against it on
   this machine with KWin stopped.
2. The same run under `act` or a scratch container, or a clear statement of what you could not
   test locally and why.
3. `.venv/bin/python scripts/verify.py` green.

## Report back

Commit SHAs, both rig summaries (KWin and Xvfb), the run time, and anything that behaves
differently between the two displays. Claude reviews before it lands.
