# Handoff: what the review of Mission and the rig in CI found (ChatGPT)

Claude reviewed `chatgpt/0-15-mission` and `chatgpt/0-15-rig-ci` merged with Grok's two branches
on a throwaway branch: the gate passed (1282 tests), every mutation spec was caught, and Month ran
9/9 on the rig. Mission is on the engine as the brief asked, and the rig branch's process ownership
is right. Each needs one change before it lands. Make them on the branches you already have, commit
locally only, and Claude reviews both again.

The two are independent and can run at the same time in their own worktrees, with two rules for the
whole computer, not just one checkout:

- One test suite at a time. Qt's test mode writes to `~/.qttest`, one folder per user, so suites in
  different worktrees fail each other. Before `scripts/verify.py` or `pytest`, check that
  `ps -eo args | grep "[p]ytest\|[v]erify.py"` prints nothing.
- No rig run from a checkout that does not have commit `6525429` (`git merge-base --is-ancestor
  6525429 HEAD`). Without it the hidden KWin breaks the owner's Alt+Tab; see part 2.

## 1. Mission: the parked hours outlive the window

Branch `chatgpt/0-15-mission`, worktree `~/.worktrees/flexweek-015-mission`.

`_detach` in `desktop/native/layouts/mission.py` takes the scroll of the tab not shown out of the
layout and calls `widget.setParent(None)`. A widget with no parent belongs to no window: when the
window closes, that scroll stays alive, and its canvas's signal connections keep the whole view
alive with it. Claude's probe (Week, then Day, then Week, then the window deleted) finds the parked
Day scroll still alive in C++ and the view still held, even after the garbage collector runs.

- Delete the `widget.setParent(None)` line. Taken out of the layout, the scroll stays a hidden
  child of the page; `empty()` only deletes what is still in the layout, so it survives re-renders
  as before and goes with the window. Claude checked this: the 12 Mission tests still pass, and the
  parked scroll is deleted with its window.
- Prove it with a test in `desktop/tests/test_layout_mission.py`: a Mission view inside a host
  widget shows Week, Day and Week; the host is deleted with `deleteLater()` followed by
  `QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)`; then
  `shiboken6.isValid(parked)` is False for the scroll that was parked (`view._scrolls["day"]`).
  `processEvents()` alone does not run deferred deletes outside an event loop, so a test that uses
  it proves nothing. Show the test failing before the fix.
- No rig run is needed for this. If you run one, merge `feat/0.15-tabs` first (see part 2).

## 2. The rig in CI: a hidden KWin must not share the desktop's D-Bus

Branch `chatgpt/0-15-rig-ci`, worktree `~/.worktrees/flexweek-015-rigci`.

A hidden `kwin_wayland --virtual` started on the desktop's session bus tries to take KDE's global
shortcut service, even with `--no-global-shortcuts`. On 23 September, between 13:28 and 13:44, twelve
hidden KWins did (`journalctl --user | grep "Failed to register service org.kde.kglobalaccel"`), and
the owner's Alt+Tab stopped working until they logged out. On 22 September the same broke
Super+Tab.

`feat/0.15-tabs` fixes this in the old launcher at `6525429`: `hidden_session.py` starts its own
`dbus-daemon`, KWin and FlexWeek run on it, and it is stopped after KWin. The daemon uses a config
with no service directories, because the stock session config starts a file-dialog portal and a
password service on demand, gives them the desktop's own display, and they outlive the bus.

1. Merge `feat/0.15-tabs` into your branch. `scripts/rig/hidden_session.py` and
   `scripts/rig/drive.py` will conflict. Keep your structure (owned processes, per-checkout state,
   Xvfb and KWin) and bring the bus into it:
   - The bus is an owned process like Xvfb and Openbox: started first, recorded in the session,
     stopped last, and checked by `_alive` like the others. Use the same no-activation config
     (`BUS_CONFIG` on `feat/0.15-tabs`) and the same command:
     `dbus-daemon --config-file=<config> --nofork --nopidfile --print-address=1`.
   - Every session has its own bus, whichever server it uses. KWin is started with its address,
     and `drive.py` gives the same address to the FlexWeek child as `DBUS_SESSION_BUS_ADDRESS`.
2. Tests in `scripts/rig/test_hidden_session.py`:
   - KWin is launched with the session's own bus address, never the one in the caller's
     environment.
   - `stop()` stops the bus after the servers, as your two-process test does for Xvfb and Openbox.
   - The bus starts nothing on demand: start it the way the launcher does and ask it
     `busctl --address=<address> call org.freedesktop.DBus /org/freedesktop/DBus
     org.freedesktop.DBus ListActivatableNames`; the answer is `as 1 "org.freedesktop.DBus"`. Skip
     only when `dbus-daemon` is not installed.
3. Prove it on this computer with KWin, one run at a time:

       SINCE=$(date "+%Y-%m-%d %H:%M:%S")
       .venv/bin/python scripts/rig/drive.py --server kwin --design classic --tab day
       journalctl --user --since "$SINCE" | grep -c "Failed to register service org.kde.kglobalaccel"

   The count must be 0 and the run 14/14. While a session is up
   (`scripts/rig/hidden_session.py --server kwin start`), `busctl --user list` must show no name
   owned by the hidden KWin's PID. After `stop`, no process may still have the private bus in its
   environment: `for d in /proc/[0-9]*; do tr '\0' '\n' < $d/environ 2>/dev/null | grep -q
   "^DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/dbus-" && ps -o pid=,args= -p ${d#/proc/}; done`
   prints nothing.
4. Your CI check that a run selected at least one scenario can stay. `drive.py` exiting 0 on an
   empty selection is Claude's to fix with the rig's other scenario work.

## Do not

- Do not edit `desktop/native/hours/*`, `spec.md`, or another design.
- Do not start the next design yet. It waits for two things from Claude, the rig aiming along
  sideways hours and a shared way for designs to remember zoom, so it does not copy Mission's
  one-off in `window.py`.
- Do not push, open a pull request, or change anything on the remote. Commit locally only.

## Report back

Commit SHAs on each branch, the failing-then-passing Mission test, the journal count and rig
summary from part 2, and anything in the merge you resolved differently from this brief, with the
reason.
