"""Retro dresses a sheet and Setup as old desktop windows: a title bar with caption buttons
that work, bevels on the controls, and a frame that is built once, owned by its page, and safe to free."""

from __future__ import annotations

import gc
import sys
from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)
from shiboken6 import isValid

from desktop.native.feel import (
    BevelPane,
    Context,
    Win98Chrome,
    Win98TitleBar,
    apply_feel,
    bevel_css,
    extra_stylesheet,
    set_current,
)
from desktop.native.look import sanitize_look
from desktop.native.setup import SetupPage
from desktop.native.widgets import HomeworkDialog
from desktop.tests.settings.support_feel import _dressed, _host
from desktop.tests.window_support import free, qapp  # noqa: F401


@pytest.fixture(autouse=True)
def nothing_is_left_dressed() -> Iterator[None]:
    yield
    set_current(None)


def test_retro_titles_its_windows_and_the_drawn_x_and_escape_close_a_sheet(
    qapp: QApplication,  # noqa: F811
) -> None:
    host, ctx = _host(qapp, "retro")
    dialog = HomeworkDialog(host, today="2026-10-01")
    dialog.show()
    apply_feel(dialog, ctx)
    qapp.processEvents()
    card = dialog.findChild(QWidget, "sheetCard")
    assert card is not None
    assert card.findChild(QWidget, "win98TitleBar") is not None
    words = card.findChild(QLabel, "win98Title")
    assert words is not None
    assert words.text() == "Add homework"
    close = card.findChild(QPushButton, "win98Cap-close")
    assert close is not None
    close.click()
    qapp.processEvents()
    assert not dialog.isVisible()
    dialog = HomeworkDialog(host, today="2026-10-01")
    dialog.show()
    apply_feel(dialog, ctx)
    qapp.processEvents()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    qapp.processEvents()
    assert not dialog.isVisible()
    free(host)




def test_retro_bevels_are_raised_and_sunken(qapp: QApplication) -> None:  # noqa: F811
    pack, look, palette, tokens, feel, base, _layout = _dressed("retro")
    extra = extra_stylesheet(base, feel, palette, tokens, look, ("sheetTitle",))
    assert "border-width: 2px" in extra
    assert bevel_css("raised") in extra
    assert bevel_css("sunken") in extra
    host, ctx = _host(qapp, "retro")
    dialog = HomeworkDialog(host, today="2026-10-01")
    dialog.show()
    apply_feel(dialog, ctx)
    qapp.processEvents()
    assert dialog.findChild(QWidget, "win98Bevels") is not None
    dialog.close()
    free(dialog)
    free(host)


class _Cycle:
    """A Python loop around a page, so only the garbage collector can free it."""

    def __init__(self, page: QWidget) -> None:
        self.page = page
        self.loop = self


def _record_errors(monkeypatch: pytest.MonkeyPatch) -> list[BaseException]:
    """Errors a Qt override raised. The app's own hook waits on the window thread, and the collector
    can run off it: that hung the app once, here it fails the assertion."""
    errors: list[BaseException] = []
    monkeypatch.setattr(sys, "excepthook", lambda _kind, value, _tb: errors.append(value))
    return errors


def test_collecting_a_retro_page_raises_nothing(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    errors = _record_errors(monkeypatch)
    host, ctx = _host(qapp, "retro")
    freed: list[bool] = []
    gc.collect()
    # The run keeps the collector off (conftest); put back whatever was set, never switch it on.
    was_on = gc.isenabled()
    # Collector off while the page is built, so what it breaks up later is in the order it was made.
    gc.disable()
    try:
        # A bare page: SetupPage holds itself in closures, so the collector never frees it.
        page = QWidget()
        page.setObjectName("settingsPage")
        QSlider(page)
        page.resize(1280, 800)
        page.show()
        apply_feel(page, ctx)
        apply_feel(page, ctx)
        qapp.processEvents()
        assert page.findChild(Win98Chrome) is not None
        assert page.findChild(BevelPane) is not None
        page.destroyed.connect(lambda *_: freed.append(True))
        held = _Cycle(page)
        del page, held
        gc.collect()
        qapp.processEvents()
    finally:
        if was_on:
            gc.enable()
    free(host)
    assert freed == [True]
    assert errors == []


def test_an_emptied_retro_frame_ignores_its_hosts_events(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    errors = _record_errors(monkeypatch)
    host, ctx = _host(qapp, "retro")
    page = QWidget()
    page.setObjectName("settingsPage")
    QSlider(page)
    page.resize(1280, 800)
    page.show()
    apply_feel(page, ctx)
    frame = page.findChild(Win98Chrome)
    assert frame is not None
    # What the collector does to an object it is breaking up, while Qt still has the C++ side.
    frame.hide()
    frame.__dict__.clear()
    page.hide()
    page.show()
    page.resize(page.width() + 8, page.height())
    free(page)
    free(host)
    assert errors == []


def test_every_retro_widget_is_owned_by_the_page_it_dresses(qapp: QApplication) -> None:  # noqa: F811
    def frames() -> dict[int, QWidget]:
        found = (Win98Chrome, Win98TitleBar, BevelPane)
        return {id(obj): obj for obj in gc.get_objects() if isinstance(obj, found) and isValid(obj)}

    host, ctx = _host(qapp, "retro")
    large = sanitize_look({**ctx.look, "knobs": {**ctx.look.get("knobs", {}), "text": "large"}})
    restyled = Context(ctx.feel, large, ctx.palette, ctx.tokens, ctx.base_sheet)
    before = frames()
    dialog = HomeworkDialog(host, today="2026-10-01")
    dialog.show()
    setup = SetupPage(host)
    setup.motion = "off"
    for root in (dialog, setup):
        apply_feel(root, ctx)
        apply_feel(root, restyled)
        qapp.processEvents()
        made = [obj for key, obj in frames().items() if key not in before and root.isAncestorOf(obj)]
        assert {type(obj) for obj in made} == {Win98Chrome, Win98TitleBar, BevelPane}, root.objectName()
    strays = [obj for key, obj in frames().items() if key not in before and obj.parentWidget() is None]
    assert strays == []
    dialog.close()
    free(dialog)
    free(setup)
    free(host)


class _PaintCount(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.count = 0

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Paint:
            self.count += 1
        return False


