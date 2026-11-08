"""Setup's rail of steps: a finished step is announced as done, a skipped one as skipped, the current one as
the current step. How the tick, dash and ring look is judged in the picture review."""

# ruff: noqa: F811  (a test's fixture parameter has the name of the imported fixture)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.setup import HOMEWORK
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.setup.support_setup_page import show_setup
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_finished_step_is_announced_as_done_on_the_rail(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    setup = show_setup(qapp, window)
    setup.next.click()
    setup.next.click()
    assert setup.step == HOMEWORK
    assert [item.accessibleDescription() for item in setup.rail_items[:3]] == ["Done", "Done", "Current step"]


def test_a_skipped_step_is_marked_skipped_not_done(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    """A step left by Skip is not done, so the rail announces it as skipped, not done."""
    setup = show_setup(qapp, window)
    setup.skip.click()
    setup.skip.click()
    assert setup.step == HOMEWORK
    assert [item.accessibleDescription() for item in setup.rail_items[:3]] == [
        "Skipped",
        "Skipped",
        "Current step",
    ]
