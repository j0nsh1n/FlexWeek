# ruff: noqa: F811
"""Running late as the window runs it: why it refuses to open, and what it says once the late start is
saved or fails to save."""

from __future__ import annotations

from datetime import datetime

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.widgets import TOAST_MS  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    qapp,  # noqa: F401
    wait_until,
    window,  # noqa: F401
)
from desktop.tests.logic_support import fail_once  # noqa: E402


def test_a_blocked_running_late_toasts_why(qapp: QApplication, window: NativeWindow) -> None:
    window.session.dirty = True
    window._open_late()
    saving = "Saving your last change… Running late will work in a moment."
    assert window.toast.isVisible() is True
    assert window.toast.text() == saving
    assert window.toast._timer.interval() == TOAST_MS

    window.session.dirty = False
    window.session.conflict = True
    window._open_late()
    conflict = "This week changed in another window. Choose More > Reload this week, then try again."
    assert window.toast.text() == conflict


def accept_late(qapp: QApplication, window: NativeWindow) -> tuple[dict, str]:
    from desktop.native.reuse import late_locked_line

    now = datetime.fromtimestamp(window.session.now_ms() / 1000)
    window.session.preview_running_late(30, now)
    wait_until(qapp, lambda: window.session.late_preview is not None and not window.session.busy)
    preview = window.session.late_preview
    moved = len((preview.get("trace") or {}).get("moves") or [])
    window._commit_late(preview)
    return preview["block"], late_locked_line(preview["block"], moved)


def test_accepting_running_late_says_locked_once_it_is_saved(
    qapp: QApplication, window: NativeWindow
) -> None:
    block, said = accept_late(qapp, window)
    assert window.session.selected_block_id == block["id"]
    # "Locked" is not said before the save answers: until then the late start is not kept anywhere.
    assert not (window.toast.isVisible() and window.toast.text() == said)
    wait_until(qapp, lambda: window.toast.isVisible() and window.toast.text() == said)
    assert window.toast.text() == said
    assert window.session.dirty is False
    assert any(item["id"] == block["id"] for item in window.session.blocks)


def test_a_save_without_the_late_start_does_not_confirm_it(qapp: QApplication, window: NativeWindow) -> None:
    """A save already in flight when Running late was accepted stores the week without it."""
    window._late_waiting = ("b-late-not-stored-yet", "Running late: 19:00–19:30 is now locked.")
    window.session.save_finished.emit(True, "Saved.")
    qapp.processEvents()
    assert window.toast.isVisible() is False


def test_a_late_start_that_fails_to_save_says_so_instead(qapp: QApplication, window: NativeWindow) -> None:
    fail_once(window.session, "POST", "/api/changes", 409)
    _block, said = accept_late(qapp, window)
    wait_until(qapp, lambda: window.toast.isVisible())
    assert window.toast.text() != said
    assert window.toast.text().startswith("Not saved.")
    assert window.session.conflict is True
