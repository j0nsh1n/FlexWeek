"""Save on the recovery codes asks on Material's own prompt what the file is, before the file dialog."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.native.account_copy import RECOVERY_KEEP
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import named, pump
from desktop.tests.window_support import qapp  # noqa: F401

CODES = ["aaaa-bbbb", "cccc-dddd"]


def _on_the_recovery_page(qapp, window: NativeWindow):
    window._show_recovery(CODES)
    pump(qapp, 30)
    bridge = window._account_bridge()
    assert bridge is not None and bridge.phase == "recovery"
    return bridge


def test_save_asks_to_keep_the_file_private_before_any_file_dialog(qapp, window, monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(window, "_pick_recovery_file", lambda: opened.append("dialog") or "")
    bridge = _on_the_recovery_page(qapp, window)
    bridge.saveCodes()
    pump(qapp, 10)
    assert bridge.ask["title"] == "Save recovery codes"
    assert bridge.ask["body"] == RECOVERY_KEEP
    assert [answer["label"] for answer in bridge.ask["answers"]] == ["Cancel", "Choose where to save"]
    assert named(window._material_page.root, "recoveryPrompt")
    assert opened == []


def test_escape_and_cancel_never_reach_the_file_dialog(qapp, window, monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(window, "_pick_recovery_file", lambda: opened.append("dialog") or "")
    bridge = _on_the_recovery_page(qapp, window)
    bridge.saveCodes()
    bridge.closeSheet()
    bridge.saveCodes()
    bridge.answer("stay")
    assert opened == [] and not bridge.ask


def test_choosing_opens_the_file_dialog_and_writes_the_codes(qapp, window, monkeypatch, tmp_path) -> None:
    target = tmp_path / "codes.txt"
    monkeypatch.setattr(window, "_pick_recovery_file", lambda: str(target))
    bridge = _on_the_recovery_page(qapp, window)
    bridge.saveCodes()
    bridge.answer("choose")
    assert target.read_text() == bridge.recoveryCodes + "\n"
    assert not bridge.ask
