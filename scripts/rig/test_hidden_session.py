"""Process ownership and server selection for the hidden real-pointer desktop."""

from __future__ import annotations

import subprocess
from dataclasses import replace

from scripts.rig import hidden_session as hidden


def test_auto_uses_xvfb_when_kwin_is_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hidden, "STATE", tmp_path / "session.json")
    monkeypatch.setattr(hidden.shutil, "which", lambda _name: None)
    monkeypatch.setattr(hidden, "_start_xvfb", lambda _env: ":73")
    monkeypatch.setattr(hidden, "_start_kwin", lambda _env: ":71")
    assert hidden.start() == ":73"


def test_switching_servers_stops_the_owned_session(monkeypatch) -> None:
    current = hidden.Session("kwin", ":71", (hidden.OwnedProcess(12345, "kwin_wayland", 1),))
    stopped = []
    monkeypatch.setattr(hidden, "_read_state", lambda: current)
    monkeypatch.setattr(hidden, "running", lambda: current.display)
    monkeypatch.setattr(hidden, "stop", lambda: stopped.append(True))
    monkeypatch.setattr(hidden, "_start_xvfb", lambda _env: ":72")
    assert hidden.start("xvfb") == ":72"
    assert stopped == [True]


def test_stop_terminates_both_recorded_processes(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hidden, "STATE", tmp_path / "session.json")
    first = subprocess.Popen(["sleep", "30"])
    second = subprocess.Popen(["sleep", "30"])
    try:
        hidden._save(hidden.Session("xvfb", ":73", (
            hidden._owned(first.pid, "sleep"), hidden._owned(second.pid, "sleep")
        )))
        hidden.stop()
        first.wait(timeout=3)
        second.wait(timeout=3)
        assert first.returncode == second.returncode == -15
        assert not hidden.STATE.exists()
    finally:
        for process in (first, second):
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=3)


def test_stop_does_not_signal_a_reused_pid(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(hidden, "STATE", tmp_path / "session.json")
    process = subprocess.Popen(["sleep", "30"])
    try:
        wrong_start = replace(hidden._owned(process.pid, "sleep"), started=0)
        hidden._save(hidden.Session("kwin", ":74", (wrong_start,)))
        hidden.stop()
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=3)
