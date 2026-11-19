"""The Add fixed time sheet is built in a quiet moment before the click, so the click only fills it in
and shows it with its dim. What a ready sheet must still get right: the times and category asked for,
focus on the title, no dim left behind, and no spare kept across a change of look or account.

Order is counted, never timed: a constructor that records what is on screen when it runs sees whether
the dim was already there.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QStandardPaths
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.look import sanitize_look
from desktop.native.motion import apply_ui_effects
from desktop.native.widgets import SheetShade
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-fixed-time-ready-test"])


@pytest.fixture(autouse=True)
def motion_is_put_back() -> Iterator[None]:
    yield
    apply_ui_effects("normal")


def shades(host: QWidget) -> list[SheetShade]:
    """The dims over `host`, found without findChildren, which would hand a sheet to the window."""
    return [child for child in host.children() if isinstance(child, SheetShade)]


def drained(qapp: QApplication) -> None:
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def spare_is_ready(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    wait_until(qapp, lambda: getattr(window, "_block_spare", None) is not None)








def test_a_change_of_look_drops_the_spare_built_in_the_old_one(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    """A spare built before Large text was chosen would open at the old size and colours."""
    spare_is_ready(qapp, window)
    old = window._block_spare
    knobs = {**window._look.get("knobs", {}), "text": "large"}
    window._look = sanitize_look({**window._look, "knobs": knobs})
    window._apply_appearance()
    spare_is_ready(qapp, window)
    assert window._block_spare is not old
