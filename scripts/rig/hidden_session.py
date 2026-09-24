"""A desktop session nobody sees, for driving FlexWeek with a real pointer.

KWin draws to a virtual screen and runs its own Xwayland. FlexWeek runs on that X display as an
ordinary X11 client, and xdotool moves that display's pointer, so a press, a move and a release take
the path a mouse's do: the X server, Qt's platform plugin, then the widget. Nothing reaches the
desktop the student is using.

    python scripts/rig/hidden_session.py start     # prints the X display, e.g. :1
    python scripts/rig/hidden_session.py stop

KWin and FlexWeek run on a D-Bus session of their own, started here and stopped with them. On the
desktop's session bus a hidden KWin tries to take over KDE's global shortcut service, even with
--no-global-shortcuts, and the desktop's Alt+Tab and Super+Tab stop working. The bus starts no
services on demand: the stock session bus would start a portal and a password service that open
windows on the desktop's own display and outlive the bus.

The session is found again by the PIDs it was started with, never by matching command lines.
"""

from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

STATE = Path("/tmp/flexweek-rig/session.json")
SOCKET = "flexweek-rig"
WIDTH, HEIGHT = 1400, 900
X11_SOCKETS = Path("/tmp/.X11-unix")
# A session bus as the stock one is, less <standard_session_servicedirs/>, so nothing is activated.
BUS_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <keep_umask/>
  <listen>unix:tmpdir=/tmp</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


def _alive(pid: int | None, name: str) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return Path(f"/proc/{pid}/comm").read_text().strip().startswith(name)
    except OSError:
        return False


def _state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except OSError, ValueError:
        return {}


def running() -> str | None:
    """The X display of the session already running, if there is one."""
    state = _state()
    if (
        _alive(state.get("pid"), "kwin_wayland")
        and _alive(state.get("bus_pid"), "dbus-daemon")
        and (X11_SOCKETS / f"X{state['display'].lstrip(':')}").exists()
    ):
        return state["display"]
    return None


def bus() -> str:
    """The address of the session's own D-Bus, for FlexWeek to use instead of the desktop's."""
    return _state()["bus"]


def _start_bus(env: dict[str, str]) -> tuple[subprocess.Popen, str]:
    config = STATE.parent / "bus.conf"
    config.write_text(BUS_CONFIG)
    daemon = subprocess.Popen(
        ["dbus-daemon", f"--config-file={config}", "--nofork", "--nopidfile", "--print-address=1"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    assert daemon.stdout is not None
    if select.select([daemon.stdout], [], [], 10)[0]:
        address = daemon.stdout.readline().decode().strip()
        if address:
            return daemon, address
    daemon.terminate()
    raise RuntimeError("The hidden session's D-Bus never gave its address.")


def _displays() -> set[str]:
    return {name[1:] for name in os.listdir(X11_SOCKETS) if name.startswith("X")}


def start() -> str:
    display = running()
    if display is not None:
        return display
    # Whatever an older or broken session left running goes first.
    stop()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    before = _displays()
    env = {key: value for key, value in os.environ.items() if key not in {"QT_IM_MODULE", "XMODIFIERS"}}
    daemon, address = _start_bus(env)
    env["DBUS_SESSION_BUS_ADDRESS"] = address
    # Left open on purpose: KWin writes to it for as long as the session runs.
    log = open(STATE.parent / "kwin.log", "w")  # noqa: SIM115
    kwin = subprocess.Popen(
        [
            "kwin_wayland",
            "--virtual",
            "--xwayland",
            "--no-lockscreen",
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
                STATE.write_text(
                    json.dumps({"pid": kwin.pid, "display": display, "bus_pid": daemon.pid, "bus": address})
                )
                return display
        if kwin.poll() is not None:
            daemon.terminate()
            raise RuntimeError(f"KWin exited; see {STATE.parent / 'kwin.log'}")
        time.sleep(0.2)
    kwin.terminate()
    daemon.terminate()
    raise RuntimeError("The hidden session's Xwayland never came up.")


def stop() -> None:
    """KWin first, then the bus it was using."""
    state = _state()
    for key, name in (("pid", "kwin_wayland"), ("bus_pid", "dbus-daemon")):
        pid = state.get(key)
        if pid is not None and _alive(pid, name):
            os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + 3
            while _alive(pid, name) and time.monotonic() < deadline:
                time.sleep(0.05)
    STATE.unlink(missing_ok=True)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "start"
    if command == "start":
        print(start())
    elif command == "stop":
        stop()
    else:
        raise SystemExit(f"unknown command {command!r}: use start or stop")
