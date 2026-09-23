"""A desktop session nobody sees, for driving FlexWeek with a real pointer.

KWin draws to a virtual screen and runs its own Xwayland. FlexWeek runs on that X display as an
ordinary X11 client, and xdotool moves that display's pointer, so a press, a move and a release take
the path a mouse's do: the X server, Qt's platform plugin, then the widget. Nothing reaches the
desktop the student is using.

    python scripts/rig/hidden_session.py start     # prints the X display, e.g. :1
    python scripts/rig/hidden_session.py stop

The session is found again by the PID it was started with, never by matching command lines.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

STATE = Path("/tmp/flexweek-rig/session.json")
SOCKET = "flexweek-rig"
WIDTH, HEIGHT = 1400, 900
X11_SOCKETS = Path("/tmp/.X11-unix")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return Path(f"/proc/{pid}/comm").read_text().strip().startswith("kwin_wayland")


def running() -> str | None:
    """The X display of the session already running, if there is one."""
    if not STATE.exists():
        return None
    state = json.loads(STATE.read_text())
    if _alive(state["pid"]) and (X11_SOCKETS / f"X{state['display'].lstrip(':')}").exists():
        return state["display"]
    return None


def _displays() -> set[str]:
    return {name[1:] for name in os.listdir(X11_SOCKETS) if name.startswith("X")}


def start() -> str:
    display = running()
    if display is not None:
        return display
    STATE.parent.mkdir(parents=True, exist_ok=True)
    before = _displays()
    env = {key: value for key, value in os.environ.items() if key not in {"QT_IM_MODULE", "XMODIFIERS"}}
    # Left open on purpose: KWin writes to it for as long as the session runs.
    log = open(STATE.parent / "kwin.log", "w")  # noqa: SIM115
    kwin = subprocess.Popen(
        [
            "kwin_wayland",
            "--virtual",
            "--xwayland",
            "--no-lockscreen",
            # Never register KDE's global shortcuts: a hidden KWin that does takes Super+Tab and the
            # rest away from the desktop it runs under, and leaves them dead when it exits.
            "--no-global-shortcuts",
            "--socket",
            SOCKET,
            "--width",
            str(WIDTH),
            "--height",
            str(HEIGHT),
        ],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        fresh = _displays() - before
        if fresh:
            display = ":" + sorted(fresh, key=int)[0]
            # Xwayland opens its socket before it takes connections.
            if (
                subprocess.run(
                    ["xdotool", "getmouselocation"], env={**env, "DISPLAY": display}, capture_output=True
                ).returncode
                == 0
            ):
                STATE.write_text(json.dumps({"pid": kwin.pid, "display": display}))
                return display
        if kwin.poll() is not None:
            raise RuntimeError(f"KWin exited; see {STATE.parent / 'kwin.log'}")
        time.sleep(0.2)
    kwin.terminate()
    raise RuntimeError("The hidden session's Xwayland never came up.")


def stop() -> None:
    if not STATE.exists():
        return
    state = json.loads(STATE.read_text())
    if _alive(state["pid"]):
        os.kill(state["pid"], signal.SIGTERM)
    STATE.unlink()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "start"
    if command == "start":
        print(start())
    elif command == "stop":
        stop()
    else:
        raise SystemExit(f"unknown command {command!r}: use start or stop")
