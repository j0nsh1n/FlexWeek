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


def start_new_copy(*, cpu: bool) -> None:
    """Start FlexWeek again the way it was started. The caller quits this copy.

    `sys.orig_argv` is the interpreter and its arguments for a source run (`python -m desktop.main ...`),
    and the program and its arguments for a frozen build.
    """
    arguments = list(sys.orig_argv) or [sys.executable, *sys.argv]
    environment = dict(os.environ)
    if cpu:
        environment[BACKEND_ENV] = SOFTWARE
        environment[NOTICE_ENV] = "1"
    else:
        environment.pop(BACKEND_ENV, None)
        environment.pop(NOTICE_ENV, None)
    subprocess.Popen(arguments, env=environment, start_new_session=True, close_fds=True)
