"""An unseen desktop for the real-pointer rig.

KWin provides Xwayland on a virtual screen locally. Xvfb and Openbox provide the same X11
interface on Linux CI. The state file records the exact processes this module started, so stop
never searches for processes by command line. Each checkout has its own state, logs and KWin
socket; the X display is allocated by the server.

    python scripts/rig/hidden_session.py --server xvfb start
    python scripts/rig/hidden_session.py stop
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import select
import shutil
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path


def _namespace(checkout: Path) -> tuple[Path, str]:
    identity = checkout.resolve().stat()
    key = f"{identity.st_dev:x}-{identity.st_ino:x}"
    return Path("/tmp/flexweek-rig") / key / "session.json", f"flexweek-rig-{key}"


STATE, SOCKET = _namespace(Path(__file__).resolve().parents[2])
WIDTH, HEIGHT = 1400, 900
X11_SOCKETS = Path("/tmp/.X11-unix")
PROC = Path("/proc")
SERVERS = ("kwin", "xvfb")
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


@dataclass(frozen=True)
class OwnedProcess:
    pid: int
    name: str
    started: int


@dataclass(frozen=True)
class Session:
    server: str
    display: str
    processes: tuple[OwnedProcess, ...]
    bus: str = ""


def _process_state(pid: int) -> tuple[str, int] | None:
    """Linux process state and start tick distinguish our PID from a later process using it."""
    try:
        fields = (PROC / str(pid) / "stat").read_text().rsplit(") ", 1)[1].split()
        return fields[0], int(fields[19])
    except (OSError, IndexError, ValueError):
        return None


def _owned(pid: int, name: str) -> OwnedProcess:
    state = _process_state(pid)
    if state is None:
        raise RuntimeError(f"{name} exited before the hidden display was ready")
    return OwnedProcess(pid, name, state[1])


def _alive(process: OwnedProcess) -> bool:
    state = _process_state(process.pid)
    if state is None or state[0] == "Z" or state[1] != process.started:
        return False
    try:
        return (PROC / str(process.pid) / "comm").read_text().strip() == process.name
    except OSError:
        return False


def _read_state() -> Session | None:
    try:
        raw = json.loads(STATE.read_text())
        if not isinstance(raw, dict):
            return None
        display = raw.get("display")
        if not isinstance(display, str) or re.fullmatch(r":[0-9]+", display) is None:
            return None
        if raw.get("server") not in SERVERS:
            return None
        processes = tuple(OwnedProcess(**item) for item in raw["processes"])
        old_count = 1 if raw["server"] == "kwin" else 2
        if len(processes) not in (old_count, old_count + 1):
            return None
        address = raw.get("bus", "")
        if not isinstance(address, str):
            return None
        return Session(raw["server"], display, processes, address)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _save(session: Session) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    pending = STATE.with_suffix(".new")
    pending.write_text(json.dumps(asdict(session)))
    pending.replace(STATE)


def running() -> str | None:
    """The display if the saved server and its window manager are still ours and alive."""
    session = _read_state()
    if (
        session is None
        or not session.bus
        or len(session.processes) != (2 if session.server == "kwin" else 3)
        or session.processes[0].name != "dbus-daemon"
        or not all(_alive(process) for process in session.processes)
    ):
        return None
    if session.server == "kwin" and _kwin_display(session.processes[-1].pid) != session.display:
        return None
    socket = X11_SOCKETS / f"X{session.display[1:]}"
    return session.display if socket.exists() else None


def bus() -> str:
    """The private bus address inherited by the hidden app, never the caller's bus."""
    session = _read_state()
    if session is None or not session.bus or running() is None:
        raise RuntimeError("No running hidden session with a private D-Bus")
    return session.bus


def _env() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key not in {"QT_IM_MODULE", "XMODIFIERS"}
    }


def _connects(display: str, env: dict[str, str]) -> bool:
    try:
        result = subprocess.run(
            ["xdotool", "getmouselocation"],
            env={**env, "DISPLAY": display},
            capture_output=True,
            timeout=2,
            check=False,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def _wait_for_display(
    display: str, env: dict[str, str], process: subprocess.Popen, seconds: int = 20
) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"The hidden X server exited; see {STATE.parent} logs")
        if _connects(display, env):
            return
        time.sleep(0.2)
    raise RuntimeError(f"The hidden X display {display} never accepted connections")


def _terminate(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def _launch(
    command: list[str], log_name: str, env: dict[str, str], *, pipe: bool = False
) -> subprocess.Popen:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with (STATE.parent / log_name).open("w") as log:
        return subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.PIPE if pipe else log,
            stderr=log,
            start_new_session=True,
        )


def _start_bus(env: dict[str, str]) -> tuple[subprocess.Popen, str]:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    config = STATE.parent / "bus.conf"
    config.write_text(BUS_CONFIG)
    daemon = _launch(
        ["dbus-daemon", f"--config-file={config}", "--nofork", "--nopidfile", "--print-address=1"],
        "bus.log",
        env,
        pipe=True,
    )
    try:
        assert daemon.stdout is not None
        if select.select([daemon.stdout], [], [], 10)[0]:
            address = daemon.stdout.readline().decode().strip()
            if address and daemon.poll() is None:
                return daemon, address
        raise RuntimeError("The hidden session's D-Bus never gave its address")
    except BaseException:
        _terminate(daemon)
        raise
    finally:
        if daemon.poll() is not None and daemon.stdout is not None:
            daemon.stdout.close()


def _kwin_display(pid: int) -> str | None:
    """Find the Xwayland display spawned by this KWin, not another checkout's."""
    for task in (PROC / str(pid) / "task").glob("*"):
        try:
            children = (task / "children").read_text().split()
        except OSError:
            continue
        for child in children:
            try:
                arguments = (PROC / child / "cmdline").read_bytes().split(b"\0")
            except OSError:
                continue
            if len(arguments) < 2 or Path(os.fsdecode(arguments[0])).name != "Xwayland":
                continue
            display = os.fsdecode(arguments[1])
            if re.fullmatch(r":[0-9]+", display):
                return display
    return None


def _start_kwin(env: dict[str, str], daemon: OwnedProcess, address: str) -> str:
    process = _launch(
        [
            "kwin_wayland", "--virtual", "--xwayland", "--no-lockscreen",
            "--no-global-shortcuts", "--socket", SOCKET,
            "--width", str(WIDTH), "--height", str(HEIGHT),
        ],
        "kwin.log",
        env,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"KWin exited; see {STATE.parent / 'kwin.log'}")
            display = _kwin_display(process.pid)
            if display and _connects(display, env):
                _save(Session("kwin", display, (daemon, _owned(process.pid, "kwin_wayland")), address))
                return display
            time.sleep(0.2)
        raise RuntimeError("The hidden session's Xwayland never came up")
    except BaseException:
        _terminate(process)
        raise


def _display_from_pipe(process: subprocess.Popen) -> str:
    """Xvfb chooses an unused display atomically and writes its number to this pipe."""
    assert process.stdout is not None
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Xvfb exited; see {STATE.parent / 'xvfb.log'}")
        if select.select([process.stdout], [], [], 0.2)[0]:
            number = process.stdout.readline().decode().strip()
            if number.isdecimal():
                process.stdout.close()
                return f":{number}"
            raise RuntimeError(f"Xvfb reported an invalid display: {number!r}")
    raise RuntimeError("Xvfb did not choose a display")


def _wait_for_openbox(env: dict[str, str], process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Openbox exited; see {STATE.parent / 'openbox.log'}")
        result = subprocess.run(
            ["xprop", "-root", "_NET_SUPPORTING_WM_CHECK"],
            env=env,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0 and "window id #" in result.stdout:
            return
        time.sleep(0.2)
    raise RuntimeError("Openbox did not take control of the hidden display")


def _start_xvfb(env: dict[str, str], daemon: OwnedProcess, address: str) -> str:
    xvfb = _launch(
        ["Xvfb", "-displayfd", "1", "-screen", "0", f"{WIDTH}x{HEIGHT}x24", "-nolisten", "tcp", "-ac"],
        "xvfb.log",
        env,
        pipe=True,
    )
    openbox = None
    try:
        display = _display_from_pipe(xvfb)
        _wait_for_display(display, env, xvfb)
        display_env = {**env, "DISPLAY": display}
        openbox = _launch(["openbox"], "openbox.log", display_env)
        _wait_for_openbox(display_env, openbox)
        _save(Session(
            "xvfb", display,
            (daemon, _owned(xvfb.pid, "Xvfb"), _owned(openbox.pid, "openbox")),
            address,
        ))
        return display
    except BaseException:
        if openbox is not None:
            _terminate(openbox)
        _terminate(xvfb)
        raise


def start(server: str = "auto") -> str:
    """Start one hidden desktop, or reuse it when it has the requested server."""
    if server == "auto":
        server = "kwin" if shutil.which("kwin_wayland") else "xvfb"
    if server not in SERVERS:
        raise ValueError(f"Unknown server {server!r}")
    current = _read_state()
    if current is not None:
        if running() is not None and current.server == server:
            return current.display
        stop()
    base_env = _env()
    daemon, address = _start_bus(base_env)
    try:
        env = {**base_env, "DBUS_SESSION_BUS_ADDRESS": address}
        owned = _owned(daemon.pid, "dbus-daemon")
        return (
            _start_kwin(env, owned, address)
            if server == "kwin"
            else _start_xvfb(env, owned, address)
        )
    except BaseException:
        _terminate(daemon)
        raise
    finally:
        if daemon.stdout is not None:
            daemon.stdout.close()


def stop() -> None:
    """Stop only PIDs that still match the processes this module started."""
    session = _read_state()
    if session is not None:
        for process in reversed(session.processes):
            if _alive(process):
                with contextlib.suppress(ProcessLookupError):
                    os.kill(process.pid, signal.SIGTERM)
                deadline = time.monotonic() + 3
                while _alive(process) and time.monotonic() < deadline:
                    time.sleep(0.1)
                if _alive(process):
                    with contextlib.suppress(ProcessLookupError):
                        os.kill(process.pid, signal.SIGKILL)
                    deadline = time.monotonic() + 3
                    while _alive(process) and time.monotonic() < deadline:
                        time.sleep(0.1)
    STATE.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", choices=("auto", *SERVERS), default="auto")
    parser.add_argument("command", nargs="?", choices=("start", "stop"), default="start")
    args = parser.parse_args()
    if args.command == "start":
        print(start(args.server))
    else:
        stop()
