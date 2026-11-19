"""The rig's command line (only --play, --out and the hidden --child are left) and its hidden session."""

from __future__ import annotations

import argparse
import json

import pytest

from scripts.rig import drive


@pytest.mark.parametrize(
    "flag",
    [
        ["--design", "classic"],
        ["--tab", "day"],
        ["--scenario", "x"],
        ["--option", "look=your"],
        ["--list"],
    ],
)
def test_the_widgets_flags_are_refused(flag, monkeypatch, capsys):
    # The Widgets interface is gone, so its flags are not options any more; argparse exits with 2.
    monkeypatch.setattr("sys.argv", ["drive.py", "--play", "p.json", *flag])
    with pytest.raises(SystemExit) as refused:
        drive.main()
    assert refused.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_without_a_play_the_rig_stops_and_names_the_flag(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["drive.py"])
    with pytest.raises(SystemExit) as refused:
        drive.main()
    assert refused.value.code == 2
    assert "--play" in capsys.readouterr().err


def test_a_play_that_asks_for_a_removed_setup_key_is_refused(tmp_path):
    for key, value in (("design", "classic"), ("look", "light-frost")):
        path = tmp_path / f"{key}.json"
        path.write_text(json.dumps({"setup": {key: value}, "steps": []}))
        with pytest.raises(SystemExit) as refused:
            drive.check_play(argparse.Namespace(play=str(path)))
        assert f"setup {key}: is not a setup key" in str(refused.value)


def _session(monkeypatch, display, bus="unix:path=/private"):
    monkeypatch.setenv("FLEXWEEK_RIG_DISPLAY", display)
    monkeypatch.setenv("FLEXWEEK_RIG_BUS", bus)
    monkeypatch.setenv("FLEXWEEK_RIG_RUNS_KEY", "abc-1")


def _clear_caller(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.delenv("FLEXWEEK_CALLER_DISPLAY", raising=False)
    monkeypatch.delenv("FLEXWEEK_CALLER_BUS", raising=False)


def test_drive_reads_the_session_fwtest_started(monkeypatch):
    _session(monkeypatch, ":71")
    _clear_caller(monkeypatch)
    assert drive.session_from_fwtest() == (":71", "unix:path=/private", "abc-1")


def test_drive_without_a_session_says_to_use_fwtest(monkeypatch):
    monkeypatch.delenv("FLEXWEEK_RIG_DISPLAY", raising=False)
    monkeypatch.delenv("FLEXWEEK_RIG_BUS", raising=False)
    monkeypatch.delenv("FLEXWEEK_RIG_RUNS_KEY", raising=False)
    with pytest.raises(SystemExit) as refused:
        drive.session_from_fwtest()
    assert str(refused.value) == "Use fwtest rig."


def test_drive_accepts_display_zero_when_the_caller_has_none(monkeypatch):
    _session(monkeypatch, ":0")
    _clear_caller(monkeypatch)
    assert drive.session_from_fwtest() == (":0", "unix:path=/private", "abc-1")


def test_drive_accepts_display_zero_allocated_for_the_session(monkeypatch):
    _session(monkeypatch, ":0")
    _clear_caller(monkeypatch)
    monkeypatch.setenv("DISPLAY", ":1")
    assert drive.session_from_fwtest() == (":0", "unix:path=/private", "abc-1")


def test_drive_refuses_display_zero_when_it_is_the_caller_display(monkeypatch):
    _session(monkeypatch, ":0")
    _clear_caller(monkeypatch)
    monkeypatch.setenv("DISPLAY", ":0")
    with pytest.raises(SystemExit) as refused:
        drive.session_from_fwtest()
    assert str(refused.value) == "Refusing display :0, which is this process's own DISPLAY."


def test_drive_keeps_an_empty_caller_display_when_the_live_one_changes(monkeypatch):
    _session(monkeypatch, ":0")
    _clear_caller(monkeypatch)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("FLEXWEEK_CALLER_DISPLAY", "")
    assert drive.session_from_fwtest() == (":0", "unix:path=/private", "abc-1")


def test_drive_refuses_the_frozen_caller_display(monkeypatch):
    _session(monkeypatch, ":0")
    _clear_caller(monkeypatch)
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setenv("FLEXWEEK_CALLER_DISPLAY", ":0")
    with pytest.raises(SystemExit) as refused:
        drive.session_from_fwtest()
    assert str(refused.value) == "Refusing display :0, which is this process's own DISPLAY."


def test_drive_refuses_the_caller_display(monkeypatch):
    _session(monkeypatch, ":1")
    _clear_caller(monkeypatch)
    monkeypatch.setenv("DISPLAY", ":1")
    with pytest.raises(SystemExit) as refused:
        drive.session_from_fwtest()
    assert str(refused.value) == "Refusing display :1, which is this process's own DISPLAY."


def test_drive_refuses_the_caller_bus(monkeypatch):
    _session(monkeypatch, ":71", "unix:path=/caller")
    _clear_caller(monkeypatch)
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/caller")
    with pytest.raises(SystemExit) as refused:
        drive.session_from_fwtest()
    assert str(refused.value) == "Refusing the caller's own D-Bus session bus."


def test_drive_keeps_an_empty_caller_bus_when_the_live_one_changes(monkeypatch):
    _session(monkeypatch, ":71")
    _clear_caller(monkeypatch)
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/private")
    monkeypatch.setenv("FLEXWEEK_CALLER_BUS", "")
    assert drive.session_from_fwtest() == (":71", "unix:path=/private", "abc-1")


def test_the_rig_forgets_the_look_an_earlier_run_left_behind():
    from pathlib import Path

    from PySide6.QtCore import QStandardPaths

    QStandardPaths.setTestModeEnabled(True)
    root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    root.mkdir(parents=True, exist_ok=True)
    left = root / "flexweek-look.json"
    left.write_text('{"preset": "terminal", "knobs": {"text": "large"}}')
    assert drive.clean_look_file() == left
    assert not left.exists()
    # Nothing left behind is not a mistake.
    assert drive.clean_look_file() == left
    assert not left.exists()


def test_the_rig_forgets_the_first_day_of_the_week_an_earlier_run_left_behind():
    from PySide6.QtCore import QStandardPaths

    from desktop.native import fields

    QStandardPaths.setTestModeEnabled(True)
    fields.save_week_starts_on("wednesday")
    assert fields.week_starts_on() == "wednesday"
    drive.clean_look_file()
    assert fields.week_starts_on() == "monday"
    drive.clean_look_file()
    assert fields.week_starts_on() == "monday"


def test_every_seed_starts_on_material_in_the_mode_the_play_asks_without_an_earlier_kept_session():
    import json

    from PySide6.QtCore import QStandardPaths

    QStandardPaths.setTestModeEnabled(True)
    kept = drive.kept_session_path()
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text('{"token": "stale"}')
    look = drive.write_material_look("dark")
    assert json.loads(look.read_text()) == {"surface": "material", "material": {"mode": "dark"}}
    # The run's server is new, so a token kept by the run before would only 401 at sign-up.
    assert not kept.exists()


def test_the_rig_forgets_the_carried_look_an_earlier_run_left_behind():
    from PySide6.QtCore import QStandardPaths

    from desktop.native.kept import KeptSession

    QStandardPaths.setTestModeEnabled(True)
    kept = KeptSession(drive.kept_session_path())
    kept.carry_look("acct-1", "large", True)
    assert kept.look.exists()
    assert kept.carried_look() == ("large", True)
    drive.clean_look_file()
    assert not kept.look.exists()
    assert kept.carried_look() is None
    drive.clean_look_file()
    assert not kept.look.exists()
