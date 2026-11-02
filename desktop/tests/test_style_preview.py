"""The style picker draws the real view while a style or an option changes, and does not save it."""

from __future__ import annotations

import importlib.util
import os
import time
from collections.abc import Callable, Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPixmap
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QRadioButton, QWidget

    from desktop.native.layouts.dialog import LayoutSection
    from desktop.native.settings import SettingsPage
    from desktop.native.style_preview import ACTUAL_NOTE, PREVIEW_DELAY_MS, Redraw, StylePreview


OPEN = {"main": "timeline", "day": "dial", "options": {}}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-style-preview-test"])
    assert isinstance(application, QApplication)
    yield application


def _sections() -> tuple[LayoutSection, LayoutSection]:
    main = LayoutSection("main", "plan", "Main view", "Plan the week.", OPEN, "system")
    day = LayoutSection("day", "day", "Day screen", "Watch the day.", OPEN, "system")
    return main, day


def _preview(sections: tuple[LayoutSection, LayoutSection], saved: list[dict]) -> StylePreview:
    main, day = sections
    preview = StylePreview(
        [main, day],
        pack=lambda: "system",
        look=lambda: None,
        on_apply=saved.append,
        delay_ms=PREVIEW_DELAY_MS,
    )
    preview.resize(360, 320)
    return preview


def _wait(ready: Callable[[], bool], timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QTest.qWait(20)
        if ready():
            return
    raise AssertionError("the preview did not catch up")


def _image(preview: StylePreview) -> QImage:
    return preview.stage.pictures[0].source.toImage()


def _child[T: QWidget](parent: QWidget, kind: type[T], name: str) -> T:
    found = parent.findChild(kind, name)
    assert found is not None, name
    return found


def test_an_option_change_redraws_after_a_short_delay_and_keeps_focus(qapp: QApplication) -> None:
    """Spacing is part of the picture. The draw waits, so a drag is not a draw on every tick, and the
    control the student is on keeps the keyboard."""
    assert PREVIEW_DELAY_MS >= 40
    saved: list[dict] = []
    main, _day = sections = _sections()
    preview = _preview(sections, saved)
    preview.show()
    _wait(lambda: not preview.stage.pictures[0].source.isNull())
    before = _image(preview)
    assert before.width() >= 1000
    compact = _child(main, QRadioButton, "layoutMain-density-compact")
    compact.click()
    for _ in range(4):
        qapp.processEvents()
    assert preview.redraw.waiting()
    assert _image(preview) == before
    assert saved == []
    fit = _child(preview, QRadioButton, "stylePreviewSize-True")
    fit.setFocus(Qt.FocusReason.TabFocusReason)
    _wait(lambda: _image(preview) != before)
    assert qapp.focusWidget() is fit
    assert preview.choice.draft["main"]["options"]["density"] == "compact"
    assert preview.choice.committed["main"]["options"]["density"] == "comfortable"
    preview.stage.zoom.buttons()[1].click()
    shown = preview.stage.pictures[0].image
    assert shown.width() == preview.stage.pictures[0].source.deviceIndependentSize().width()
    assert preview.stage.note.text() == ACTUAL_NOTE
    day = _child(preview, QRadioButton, "stylePreviewSurface-day")
    main_picture = _image(preview)
    day.click()
    _wait(lambda: _image(preview) != main_picture)
    assert preview.stage.surface_id() == "day"
    preview.close()


def test_a_redraw_superseded_while_painting_is_dropped(qapp: QApplication) -> None:
    """The picture that was already underway when a newer request arrived is not the one on screen."""
    shown: list[QPixmap] = []
    started = False
    held: list[Redraw] = []

    def paint() -> QPixmap:
        nonlocal started
        if not started:
            started = True
            held[0].ask()
            qapp.processEvents()
            stale = QPixmap(4, 4)
            stale.fill(Qt.GlobalColor.blue)
            return stale
        fresh = QPixmap(8, 8)
        fresh.fill(Qt.GlobalColor.red)
        return fresh

    host = QWidget()
    held.append(Redraw(paint, shown.append, 0, host))
    held[0].ask()
    for _ in range(6):
        qapp.processEvents()
    assert held[0].dropped >= 1
    assert [picture.width() for picture in shown] == [8]
    held.clear()
    host.deleteLater()
    qapp.processEvents()


def test_an_option_change_is_not_saved_before_apply(qapp: QApplication) -> None:
    """Trying a spacing updates the draft. The saved choice stays until Apply, and leaving puts the
    draft back."""
    saved: list[dict] = []
    main, _day = sections = _sections()
    preview = _preview(sections, saved)
    main.show()
    compact = _child(main, QRadioButton, "layoutMain-density-compact")
    compact.click()
    qapp.processEvents()
    assert saved == []
    assert preview.choice.draft["main"]["options"]["density"] == "compact"
    assert preview.choice.committed["main"]["options"]["density"] == "comfortable"
    restored = preview.discard()
    assert saved == []
    assert restored["main"]["options"]["density"] == "comfortable"
    assert preview.choice.draft["main"]["options"]["density"] == "comfortable"
    preview.refresh()
    assert saved == []
    assert preview.choice.draft["main"]["options"]["density"] == "compact"
    preview.apply()
    assert len(saved) == 1
    assert saved[0]["main"]["options"]["density"] == "compact"
    assert preview.choice.committed["main"]["options"]["density"] == "compact"
    main.close()


def test_the_preview_fits_a_short_window_at_large_text_with_motion_off(qapp: QApplication) -> None:
    """1024 by 640, Large text, animations off: the picture is on screen, named, and reachable."""
    page = SettingsPage(None, {}, {}, {})
    font = page.font()
    font.setPointSize(16 if font.pointSize() < 0 else max(font.pointSize(), 16))
    page.setFont(font)
    page.knobs["text"].setCurrentIndex(page.knobs["text"].findData("large"))
    page.motion.setCurrentIndex(page.motion.findData("off"))
    page.motion_level = "off"
    page.resize(1024, 640)
    page.show()
    preview = page.style_preview
    _wait(lambda: preview.isVisible() and not preview.stage.pictures[0].source.isNull())
    assert page.width() <= 1024
    assert page.height() <= 640
    origin = preview.mapTo(page, preview.rect().topLeft())
    corner = preview.mapTo(page, preview.rect().bottomRight())
    assert preview.width() >= 160
    assert preview.height() >= 100
    assert origin.x() >= 0
    assert origin.y() >= 0
    assert corner.x() <= page.width()
    assert corner.y() <= page.height()
    stage = _child(preview, QWidget, "stylePreview")
    zoom = _child(preview, QWidget, "stylePreviewSize")
    surface = _child(preview, QWidget, "stylePreviewSurface")
    assert stage.accessibleName() == "Style preview"
    assert zoom.accessibleName() == "Preview size"
    assert surface.accessibleName() == "Preview"
    fit = _child(preview, QRadioButton, "stylePreviewSize-True")
    assert fit.accessibleName() == "Fit"
    assert fit.isVisible()
    assert fit.width() > 20
    fit.setFocus(Qt.FocusReason.TabFocusReason)
    assert qapp.focusWidget() is fit
    page.nav.setCurrentRow(1)
    qapp.processEvents()
    assert preview.isVisible() is False
    page.nav.setCurrentRow(0)
    qapp.processEvents()
    assert preview.isVisible() is True
    page.close()
