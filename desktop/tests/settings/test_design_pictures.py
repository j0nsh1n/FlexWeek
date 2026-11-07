"""The pictures of each design in setup and Settings are built and freed whole, are of the design once
it has finished laying out, and the sample week files Soccer under Sports. How the Today's app picture
is coloured in High contrast is judged on the pictures in pictures/screens_settings_preview.py."""

from __future__ import annotations

import gc

import pytest
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

from desktop.native.layouts.registry import LAYOUTS
from desktop.native.previews import CANVAS, render, sample_week
from desktop.tests.settings.support_previews import settled_image
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.mark.parametrize("main", ["classic", "timeline"])
def test_a_picture_leaves_nothing_alive_for_the_garbage_collector(qapp: QApplication, main: str) -> None:  # noqa: F811
    """A Qt object left alive in a reference cycle is freed whenever Python's collector next runs,
    which can be in the middle of painting the window. In the rig that hung the app. Whatever a picture
    builds is gone once it is drawn, not waiting for the collector."""
    gc.collect()
    gc.set_debug(gc.DEBUG_SAVEALL)
    try:
        picture = render(main, None, "system", None, 240)
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        gc.collect()
        alive = [
            f"{type(item).__name__} {item.objectName()!r}"
            for item in gc.garbage
            if isinstance(item, QObject) and isValid(item)
        ]
    finally:
        gc.set_debug(0)
        gc.garbage.clear()
        gc.collect()
    assert not picture.isNull()
    assert alive == []


@pytest.mark.parametrize("main", list(LAYOUTS))
def test_a_picture_is_of_the_design_once_it_has_finished_laying_out(
    qapp: QApplication,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    main: str,
) -> None:
    """The designs finish laying out on the event loop, at the size they are given. Taken before the loop
    ran, Mission control's picture showed its page's scroll bar beside a half-laid-out table, and
    Timeline's its days' short names over the wrong hours. A picture is the design as it settles: what the
    view shows once the loop has run on."""
    grab = QWidget.grab
    taken = []

    def grab_and_wait(widget: QWidget, *args: object) -> object:
        picture = grab(widget, *args)
        taken.append((picture.toImage(), settled_image(lambda: grab(widget, *args).toImage())))
        return picture

    monkeypatch.setattr(QWidget, "grab", grab_and_wait)
    render(main, None, "system", None, CANVAS.width())
    [(picture, later)] = taken
    assert picture == later


def test_the_preview_week_puts_soccer_in_sports() -> None:
    _monday, blocks, _homework = sample_week()
    soccer = next(block for block in blocks if block["id"] == "soccer")
    assert soccer["category"] == "exercise"
