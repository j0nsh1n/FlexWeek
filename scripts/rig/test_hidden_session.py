"""Process ownership and server selection for the hidden real-pointer desktop."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from scripts.rig import hidden_session as hidden


def _copy_into_checkout(root: Path):
    script = root / "scripts" / "rig" / "hidden_session.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(hidden.__file__, script)
    name = f"rig_checkout_{root.name}"
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_each_checkout_has_its_own_state_and_socket(tmp_path) -> None:
    first = _copy_into_checkout(tmp_path / "first")
    second = _copy_into_checkout(tmp_path / "second")
    assert first.STATE != second.STATE
    assert first.SOCKET != second.SOCKET
    assert Path("/tmp/flexweek-rig/session.json") != first.STATE
    assert first.STATE.parent != second.STATE.parent


def test_kwin_display_comes_from_its_xwayland_child(monkeypatch, tmp_path) -> None:
    proc = tmp_path / "proc"
    own_tasks = proc / "42" / "task" / "42"
    own_tasks.mkdir(parents=True)
    (own_tasks / "children").write_text("77")
    (proc / "77").mkdir()
    (proc / "77" / "cmdline").write_bytes(b"/usr/bin/Xwayland\0:76\0")
    (proc / "88").mkdir()
    (proc / "88" / "cmdline").write_bytes(b"/usr/bin/Xwayland\0:75\0")
    monkeypatch.setattr(hidden, "PROC", proc)
    assert hidden._kwin_display(42) == ":76"


def test_running_rejects_a_display_no_longer_owned_by_kwin(monkeypatch, tmp_path) -> None:
    session = hidden.Session("kwin", ":71", (hidden.OwnedProcess(42, "kwin_wayland", 1),))
    (tmp_path / "X71").touch()
    monkeypatch.setattr(hidden, "X11_SOCKETS", tmp_path)
    monkeypatch.setattr(hidden, "_read_state", lambda: session)
    monkeypatch.setattr(hidden, "_alive", lambda _process: True)
    monkeypatch.setattr(hidden, "_kwin_display", lambda _pid: ":72")
    assert hidden.running() is None


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
