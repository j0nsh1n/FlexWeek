"""Drive FlexWeek with a real pointer on a hidden desktop, from a play file.

    fwtest rig --play PLAY.json [--out DIR]                 # an agent's own steps; see play.py

The app starts as a student's would, on Material 3, and the steps in the play run on the hidden
session's X display with xdotool. Without --out, results land in
~/.flexweek-ui-harness/scratch/plays/<time>-<play name>/.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import traceback
from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path

# The app the rig drives rings reminders; they play at no volume (desktop/native/sound.py).
os.environ["FLEXWEEK_SILENT"] = "1"

MARKER = "rig-week-marker"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from play import PlayError, default_play_folder, load_play, run_play  # noqa: E402

PASSWORD = "a-long-test-password"


def kept_session_path() -> Path:
    """Where this rig run's kept session (and its carried look) live under Qt test-mode AppData."""
    from PySide6.QtCore import QStandardPaths

    root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    return root / "signed-in" / "flexweek.json"


def clean_look_file() -> Path:
    """The look an earlier run left behind (its zoom and text size) is gone before this one starts, so a
    play sees only the look it asks for. Also deletes the carried look next to the kept session
    (`flexweek.look.json`), and the first day of the week an earlier play picked, which lives in the same
    folder and would otherwise open every later run in that week. Call after QStandardPaths' test mode
    is on."""
    from PySide6.QtCore import QStandardPaths

    from desktop.native.kept import KeptSession

    root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    look_path = Path(root) / "flexweek-look.json"
    look_path.unlink(missing_ok=True)
    (Path(root) / "week-start.json").unlink(missing_ok=True)
    KeptSession(kept_session_path()).look.unlink(missing_ok=True)
    return look_path


def write_material_look(mode: str) -> Path:
    """The look file the window reads on start: Material, light or dark as the play asks.

    Every run has a new server and an empty database, so an earlier run's kept token would 401 and
    leave the card on "Please sign in again", where signing up never reaches the recovery codes.
    The kept session is removed for every seed.
    """
    from PySide6.QtCore import QStandardPaths

    kept_session_path().unlink(missing_ok=True)
    root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    root.mkdir(parents=True, exist_ok=True)
    look_path = root / "flexweek-look.json"
    look_path.write_text(json.dumps({"surface": "material", "material": {"mode": mode}}) + "\n")
    return look_path



def check_play(args: argparse.Namespace) -> None:
    """Refuse a play that cannot run, with every mistake named, before a session is started for it."""
    path = Path(args.play).expanduser().resolve()
    try:
        load_play(path)
    except PlayError as wrong:
        raise SystemExit(f"{path}:\n{wrong}") from None
    args.play = str(path)


def caller_env(frozen: str, live: str) -> str:
    """Environment `fwtest rig` started with. An empty stored value means the caller had none."""
    if frozen in os.environ:
        return os.environ[frozen]
    return os.environ.get(live, "")


def session_from_fwtest() -> tuple[str, str, str]:
    """Display, private bus, and runs-folder key passed in by `fwtest rig`."""
    display = os.environ.get("FLEXWEEK_RIG_DISPLAY", "")
    bus = os.environ.get("FLEXWEEK_RIG_BUS", "")
    runs_key = os.environ.get("FLEXWEEK_RIG_RUNS_KEY", "")
    if not display or not bus or not runs_key:
        raise SystemExit("Use fwtest rig.")
    own_display = caller_env("FLEXWEEK_CALLER_DISPLAY", "DISPLAY")
    if own_display and display == own_display:
        raise SystemExit(f"Refusing display {display}, which is this process's own DISPLAY.")
    own_bus = caller_env("FLEXWEEK_CALLER_BUS", "DBUS_SESSION_BUS_ADDRESS")
    if own_bus and bus == own_bus:
        raise SystemExit("Refusing the caller's own D-Bus session bus.")
    return display, bus, runs_key


def seed_rig_week(app: object, session: object) -> None:
    """The rig's week: school and soccer, three homework items, and the essay pinned on Thursday evening."""
    from desktop.native.calendar import sunday_due
    from desktop.tests.logic_support import wait_until

    due_sunday = sunday_due(session.week_start)
    due_friday = (
        datetime.fromisoformat(session.week_start) + timedelta(days=4)
    ).date().isoformat() + "T23:59"
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    session.add_block(
        {
            "id": "soccer",
            "title": "Soccer",
            "kind": "locked",
            "category": "exercise",
            "start": "16:00",
            "duration_min": 90,
            "days": [1, 3],
        }
    )
    for key, title, due in (
        ("essay", "History essay", due_sunday),
        ("math", "Math worksheet", due_sunday),
        ("poster", "Science poster", due_friday),
    ):
        session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    wait_until(app, lambda: not session.busy and not session.dirty, 20)
    essay = next(b for b in session.blocks if b.get("assignment_id") == "essay")
    session.add_block({**essay, "start": "19:00", "days": [3], "pinned": True})
    session.save()
    wait_until(app, lambda: not session.busy and not session.dirty, 20)


Step = Generator[tuple, object]


def child_main(args: argparse.Namespace) -> int:
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QApplication

    QStandardPaths.setTestModeEnabled(True)
    app = QApplication(["flexweek-rig"])
    clean_look_file()
    python_errors: list[str] = []

    def on_error(kind: type, value: BaseException, tb: object) -> None:
        python_errors.append(f"{getattr(kind, '__name__', kind)}: {value}")
        traceback.print_exception(kind, value, tb)
        app.quit()

    sys.excepthook = on_error

    from desktop.native.kept import KeptSession
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer
    from desktop.tests.logic_support import past_recovery, sign_up

    out = Path(args.out)
    server = LocalServer(Path(tempfile.mkdtemp()) / "rig.db")
    server.start()
    play = load_play(Path(args.play))
    material_new = play.setup.seed == "material-new"
    write_material_look(play.setup.mode)
    window = NativeWindow(server.origin, kept=KeptSession(kept_session_path()))
    window.resize(1280, 820)
    window.move(0, 0)
    window.show()
    if material_new:
        return run_play(app, window, window.session, server, out, play, seed_rig_week, python_errors)
    sign_up(app, window, "rig_student", PASSWORD)
    past_recovery(app, window)
    return run_play(app, window, window.session, server, out, play, seed_rig_week, python_errors)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out")
    parser.add_argument(
        "--play",
        required=True,
        metavar="PLAY.json",
        help="run the steps in this file and record each (see docs/tooling/fwtest.md, Playing the app)",
    )
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    check_play(args)
    if args.child:
        return child_main(args)
    display, bus, _runs_key = session_from_fwtest()
    return drive(args, display, bus)


def drive(args: argparse.Namespace, display: str, bus: str) -> int:
    """Run the play in a child on the hidden display, and return its exit code."""
    out = Path(args.out) if args.out else default_play_folder(Path(args.play).stem, datetime.now())
    out.mkdir(parents=True, exist_ok=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"WAYLAND_DISPLAY", "QT_IM_MODULE", "XMODIFIERS"}
    }
    # XInput 2 off: on the hidden display Qt never hears xdotool's wheel through it, only through
    # the core protocol, and plays that turn the wheel need it. Presses and drags arrive either way.
    env.update(
        DISPLAY=display,
        DBUS_SESSION_BUS_ADDRESS=bus,
        QT_QPA_PLATFORM="xcb",
        QT_XCB_NO_XI2="1",
        XDG_DATA_HOME=str(out / "data"),
        PYTHONFAULTHANDLER="1",
    )
    command = [sys.executable, __file__, "--child", "--out", str(out), "--play", args.play]
    return subprocess.run(command, env=env, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
