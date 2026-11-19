"""Drive FlexWeek with a real pointer on a hidden desktop, from a play file.

    fwtest rig --play PLAY.json [--out DIR]                 # an agent's own steps; see play.py

The app starts as a student's would, on Material 3, and the steps in the play run on the hidden
session's X display with xdotool. Without --out, results land in
~/.flexweek-ui-harness/scratch/rig-runs/<checkout id>/ (FLEXWEEK_RIG_RUNS names another folder),
and the newest 3 runs of the checkout are kept.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
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

DESIGNS = ("classic",)
TABS = ("day", "week", "month")
PASSWORD = "a-long-test-password"
KEEP_RUNS = 3
RUN_NAME = re.compile(r"\d{8}-\d{6}-\d+")


def parse_options(design: str | None, pairs: list[str]) -> dict[str, str]:
    """`--option key=value` pairs as the design's saved options, or a SystemExit naming what is valid."""
    from desktop.native.layout_choice import LAYOUTS

    if not pairs:
        return {}
    if design not in LAYOUTS:
        raise SystemExit("--option sets a design's option, so it needs --design (a design with options).")
    spec = LAYOUTS[design]
    valid = {option.key: option.values for option in spec.options}
    listing = "; ".join(f"{key}: {', '.join(values)}" for key, values in valid.items()) or "none"
    chosen: dict[str, str] = {}
    for pair in pairs:
        key, separator, value = pair.partition("=")
        if not separator:
            raise SystemExit(f"--option {pair!r} is not key=value. {design} options: {listing}")
        if key not in valid:
            raise SystemExit(f"{design} has no option {key!r}. {design} options: {listing}")
        if value not in valid[key]:
            raise SystemExit(
                f"{design} option {key!r} has no value {value!r}. Valid: {', '.join(valid[key])}"
            )
        chosen[key] = value
    return chosen


def play_looks() -> tuple[str, ...]:
    """The names a play's "look" may take: a look preset or a theme pack."""
    from desktop.native.look import LOOK_PRESETS, PACKS

    return (*(name for name in LOOK_PRESETS if name != "default"), *PACKS)


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


def write_material_new_look(mode: str) -> Path:
    """Material is the saved surface, and nobody is signed in.

    An earlier rig run's kept token would 401 against this empty database and write
    "Please sign in again" on the card, so that file is removed too.
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
    if not args.play:
        return
    if args.design or args.tab or args.scenario or args.option or args.list:
        raise SystemExit(
            "--play runs its own steps; --design, --tab, --scenario, --option and --list do not mix with it."
        )
    path = Path(args.play).expanduser().resolve()
    try:
        load_play(path, DESIGNS, play_looks())
    except PlayError as wrong:
        raise SystemExit(f"{path}:\n{wrong}") from None
    args.play = str(path)


def default_runs_folder(runs_key: str) -> Path:
    # Runs live on disk, not in /tmp: on Jonathan's machine /tmp is RAM (tmpfs with zram swap) and a
    # day of rig runs held 767 MB of it. FLEXWEEK_RIG_RUNS moves them, since that harness folder
    # exists only there. The hidden session's own state is small and stays in /tmp.
    root = os.environ.get("FLEXWEEK_RIG_RUNS")
    base = Path(root) if root else Path.home() / ".flexweek-ui-harness" / "scratch" / "rig-runs"
    return base / runs_key


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


def prune_runs(folder: Path) -> None:
    runs = sorted(item for item in folder.iterdir() if item.is_dir() and RUN_NAME.fullmatch(item.name))
    for old in runs[:-KEEP_RUNS]:
        shutil.rmtree(old, ignore_errors=True)


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
    play = load_play(Path(args.play), DESIGNS, play_looks()) if args.play else None
    if play is None:
        server.stop()
        if not args.list:
            print("Give a play to run: --play PLAY.json (see docs/tooling/fwtest.md).", file=sys.stderr)
        return 0 if args.list else 2
    material_new = play.setup.seed == "material-new"
    if material_new:
        write_material_new_look(play.setup.mode)
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
    parser.add_argument("--design", choices=DESIGNS)
    parser.add_argument("--tab", choices=TABS)
    parser.add_argument("--scenario")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--out")
    parser.add_argument(
        "--option",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="set one of --design's saved options, e.g. hero=today; repeat for more",
    )
    parser.add_argument(
        "--play",
        metavar="PLAY.json",
        help="run the steps in this file and record each (see docs/tooling/fwtest.md, Playing the app)",
    )
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    parse_options(args.design, args.option)
    check_play(args)
    if args.list and not args.child:
        args.out = tempfile.mkdtemp()
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if args.child or args.list:
        return child_main(args)
    display, bus, runs_key = session_from_fwtest()
    return drive(args, display, bus, runs_key)


def drive(args: argparse.Namespace, display: str, bus: str, runs_key: str) -> int:
    """Run the scenarios in a child on the hidden display, and return its exit code."""
    runs = None if args.out or args.play else default_runs_folder(runs_key)
    if args.out:
        out = Path(args.out)
    elif args.play:
        out = default_play_folder(Path(args.play).stem, datetime.now())
    else:
        out = runs / f"{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
    out.mkdir(parents=True, exist_ok=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"WAYLAND_DISPLAY", "QT_IM_MODULE", "XMODIFIERS"}
    }
    # XInput 2 off: on the hidden display Qt never hears xdotool's wheel through it, only through
    # the core protocol, and the zoom scenarios turn the wheel. Presses and drags arrive either way.
    env.update(
        DISPLAY=display,
        DBUS_SESSION_BUS_ADDRESS=bus,
        QT_QPA_PLATFORM="xcb",
        QT_XCB_NO_XI2="1",
        XDG_DATA_HOME=str(out / "data"),
        PYTHONFAULTHANDLER="1",
    )
    command = [sys.executable, __file__, "--child", "--out", str(out)]
    for flag in ("design", "tab", "scenario"):
        if getattr(args, flag):
            command += [f"--{flag}", getattr(args, flag)]
    for pair in args.option:
        command += ["--option", pair]
    if args.play:
        command += ["--play", args.play]
    try:
        return subprocess.run(command, env=env, cwd=ROOT).returncode
    finally:
        if runs is not None:
            prune_runs(runs)


if __name__ == "__main__":
    raise SystemExit(main())
