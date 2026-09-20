"""Starting FlexWeek when the student logs in.

"Start FlexWeek when I log in" was a checkbox that saved a value on the account and did nothing on
any machine. Honouring it means writing something the desktop environment reads at login, which is
per-platform: an autostart .desktop file on Linux, a Run key on Windows.

The decisions here are separated from the writing so they can be checked without touching a real
login: entry_text and launch_command are pure, and sync takes the directory to work in.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import shutil
import sys
from pathlib import Path
from typing import Any

ENTRY_NAME = "flexweek.desktop"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "FlexWeek"


def frozen() -> bool:
    """True in a packaged build, where the executable is FlexWeek itself."""
    return bool(getattr(sys, "frozen", False) or globals().get("__compiled__"))


def launch_command(argv: list[str] | None = None, executable: str | None = None) -> str:
    """What to run at login. In a bundle that is the executable; from a source checkout it is this
    interpreter and the entry script, so a developer's autostart does not point at bare python."""
    binary = executable if executable is not None else sys.executable
    if frozen():
        return _quote(binary)
    args = list(sys.argv if argv is None else argv)
    script = Path(args[0]).resolve() if args and args[0] else Path("desktop/main.py").resolve()
    return f"{_quote(binary)} {_quote(str(script))}"


def _quote(value: str) -> str:
    return f'"{value}"' if " " in value else value


def entry_text(command: str) -> str:
    """An XDG autostart entry. Kept in step with packaging/flexweek.desktop, except for Exec, which
    has to be the real path: a bare "FlexWeek" only resolves if the bundle is on PATH."""
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=FlexWeek\n"
        "Comment=Plan a school week and let the solver place your work\n"
        f"Exec={command}\n"
        "Icon=flexweek\n"
        "Terminal=false\n"
        "Categories=Office;Calendar;Qt;\n"
        "StartupNotify=true\n"
        "StartupWMClass=flexweek\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def autostart_dir() -> Path:
    """Where XDG says login entries live."""
    config = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(config) / "autostart"


def sync(enabled: bool, *, command: str | None = None, directory: Path | None = None) -> Path | None:
    """Write or remove the login entry. Returns the path it settled on, or None when the platform has
    no handling here. Never raises: a read-only home must not stop the settings dialog from saving."""
    if sys.platform.startswith("win") and directory is None:
        return _sync_windows(enabled, command)
    if sys.platform == "darwin" and directory is None:
        # macOS wants a LaunchAgent plist, which this project does not ship or test yet.
        return None
    target = (directory if directory is not None else autostart_dir()) / ENTRY_NAME
    try:
        if not enabled:
            target.unlink(missing_ok=True)
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(entry_text(command or launch_command()), encoding="utf-8")
        # An entry the desktop will not execute is the same as no entry at all.
        target.chmod(0o755)
    except OSError:
        return None
    return target


def enabled_on_disk(directory: Path | None = None) -> bool:
    """Whether a login entry is actually in place, which is what the machine will obey."""
    if sys.platform.startswith("win") and directory is None:
        return _windows_value() is not None
    if sys.platform == "darwin" and directory is None:
        return False
    return ((directory if directory is not None else autostart_dir()) / ENTRY_NAME).exists()


def _sync_windows(enabled: bool, command: str | None) -> Path | None:
    """Windows has no autostart folder convention the way XDG does; it has a Run key. Written here,
    unverified on this machine: it needs a hand-check on a real Windows PC."""
    registry = _winreg()
    if registry is None:
        return None
    try:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, RUN_KEY, 0, registry.KEY_SET_VALUE) as key:
            if enabled:
                registry.SetValueEx(key, RUN_VALUE, 0, registry.REG_SZ, command or launch_command())
            else:
                with contextlib.suppress(FileNotFoundError):
                    registry.DeleteValue(key, RUN_VALUE)
    except OSError:
        return None
    return Path(RUN_KEY) / RUN_VALUE


def _windows_value() -> str | None:
    registry = _winreg()
    if registry is None:
        return None
    try:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, RUN_KEY) as key:
            return str(registry.QueryValueEx(key, RUN_VALUE)[0])
    except OSError:
        return None


def _winreg() -> Any:
    """winreg ships only on Windows, and lint and type checking run on Linux, so it is reached
    through a name the checkers do not try to resolve against a module that is not there."""
    if sys.platform != "win32":
        return None
    return importlib.import_module("winreg")


def command_exists(command: str) -> bool:
    """A sanity check for the command that was written, used only by diagnostics."""
    head = command.split('"')[1] if command.startswith('"') else command.split(" ")[0]
    return bool(shutil.which(head) or Path(head).exists())
