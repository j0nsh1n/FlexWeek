"""Drawing Material on the CPU when the graphics card or its driver cannot be used.

The look file remembers the app version that failed. That version starts with Qt Quick's software
drawing; a newer version tries the graphics card again.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

LOOK_KEY = "cpu_drawing_version"
BACKEND_ENV = "QT_QUICK_BACKEND"
SOFTWARE = "software"
# Set only on the copy started after a failure, so its first Material screen can say why once.
NOTICE_ENV = "FLEXWEEK_CPU_NOTICE"
NOTICE = "FlexWeek is drawing without the graphics card because it could not use it. Your week is unchanged."
DRAW_ERROR = "FlexWeek could not draw its window, even without the graphics card."


def drawing_on_cpu() -> bool:
    return os.environ.get(BACKEND_ENV) == SOFTWARE


def saved_version(stored: object) -> str:
    value = stored.get(LOOK_KEY) if isinstance(stored, dict) else None
    return value if isinstance(value, str) else ""


def apply_saved(look_path: Path, version: str) -> bool:
    """Before Qt Quick starts: draw on the CPU when the look file says this version must."""
    try:
        stored = json.loads(look_path.read_text())
    except OSError, ValueError:
        return False
    if saved_version(stored) != version:
        return False
    os.environ[BACKEND_ENV] = SOFTWARE
    return True


def new_copy_command(
    *, frozen: bool, appimage: str | None, executable: str, argv: list[str], orig_argv: list[str]
) -> list[str]:
    """The command that starts FlexWeek again the way it was started.

    An AppImage runs from a mount that goes away once this copy quits, so the new copy starts from the
    AppImage file itself. A packaged build is its executable. A source run repeats the interpreter and
    its arguments (`python -m desktop.main ...`).
    """
    if frozen:
        program = appimage if appimage else executable
        return [program, *argv[1:]]
    return list(orig_argv) or [executable, *argv]


def start_new_copy(*, cpu: bool) -> None:
    """Start FlexWeek again the way it was started. The caller quits this copy."""
    from desktop.native.autostart import frozen

    arguments = new_copy_command(
        frozen=frozen(),
        appimage=os.environ.get("APPIMAGE"),
        executable=sys.executable,
        argv=list(sys.argv),
        orig_argv=list(sys.orig_argv),
    )
    environment = dict(os.environ)
    if cpu:
        environment[BACKEND_ENV] = SOFTWARE
        environment[NOTICE_ENV] = "1"
    else:
        environment.pop(BACKEND_ENV, None)
        environment.pop(NOTICE_ENV, None)
    subprocess.Popen(arguments, env=environment, start_new_session=True, close_fds=True)
