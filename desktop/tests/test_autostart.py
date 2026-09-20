"""Starting FlexWeek at login, which was a checkbox that saved a value and changed nothing.

The writing is pointed at a temporary directory, so these run without touching a real login.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from desktop.native import autostart


def test_turning_it_on_writes_an_entry_the_desktop_will_read(tmp_path: Path) -> None:
    target = autostart.sync(True, command="/opt/flexweek/FlexWeek", directory=tmp_path)
    assert target is not None and target.exists()
    text = target.read_text(encoding="utf-8")
    assert text.startswith("[Desktop Entry]")
    assert "Exec=/opt/flexweek/FlexWeek" in text
    assert autostart.enabled_on_disk(tmp_path) is True


def test_turning_it_off_takes_the_entry_away(tmp_path: Path) -> None:
    autostart.sync(True, command="/opt/flexweek/FlexWeek", directory=tmp_path)
    autostart.sync(False, directory=tmp_path)
    assert autostart.enabled_on_disk(tmp_path) is False


def test_turning_it_off_when_it_was_never_on_is_not_an_error(tmp_path: Path) -> None:
    assert autostart.sync(False, directory=tmp_path) is not None
    assert autostart.enabled_on_disk(tmp_path) is False


def test_the_entry_names_a_real_path_rather_than_a_bare_command(tmp_path: Path) -> None:
    """packaging/flexweek.desktop says Exec=FlexWeek, which only resolves if the bundle is on PATH.
    An autostart entry that does not resolve fails silently at login, which is the worst case."""
    autostart.sync(True, directory=tmp_path)
    exec_line = next(
        line
        for line in (tmp_path / autostart.ENTRY_NAME).read_text(encoding="utf-8").splitlines()
        if line.startswith("Exec=")
    )
    assert exec_line != "Exec=FlexWeek"
    assert autostart.command_exists(exec_line.removeprefix("Exec="))


def test_the_entry_is_executable_because_an_unreadable_one_is_no_entry(tmp_path: Path) -> None:
    target = autostart.sync(True, command="/opt/flexweek/FlexWeek", directory=tmp_path)
    assert target is not None
    assert target.stat().st_mode & 0o111


def test_a_read_only_home_reports_failure_rather_than_raising(tmp_path: Path) -> None:
    """The settings dialog must still save the rest of its preferences."""
    blocked = tmp_path / "blocked"
    blocked.mkdir(mode=0o500)
    if sys.platform != "win32" and autostart.sync(True, command="x", directory=blocked) is not None:
        pytest.skip("running as a user that can write anywhere")
    assert autostart.sync(True, command="x", directory=blocked) is None


def test_running_from_a_checkout_points_at_the_script_not_bare_python() -> None:
    command = autostart.launch_command(
        argv=["/home/s/FlexWeek/desktop/main.py"], executable="/usr/bin/python3"
    )
    assert command == "/usr/bin/python3 /home/s/FlexWeek/desktop/main.py"


def test_a_path_with_a_space_in_it_is_quoted() -> None:
    command = autostart.launch_command(
        argv=["/home/s/My Files/desktop/main.py"], executable="/usr/bin/python3"
    )
    assert '"/home/s/My Files/desktop/main.py"' in command
