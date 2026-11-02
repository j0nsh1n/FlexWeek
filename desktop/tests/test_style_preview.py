"""The style picker draws the real view while a style, an option, or the accent changes."""

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
    from PySide6.QtWidgets import QApplication, QComboBox, QRadioButton, QWidget

    from desktop.native.layouts.dialog import LayoutSection
    from desktop.native.settings import SettingsPage
    from desktop.native.style_preview import ACTUAL_NOTE, Redraw, StylePreview


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


def _preview(sections: tuple[LayoutSection, LayoutSection]) -> StylePreview:
    main, day = sections
    preview = StylePreview([main, day], pack=lambda: "system", look=lambda: None)
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
    main, _day = sections = _sections()
    preview = _preview(sections)
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
    fit = _child(preview, QRadioButton, "stylePreviewSize-True")
    fit.setFocus(Qt.FocusReason.TabFocusReason)
    _wait(lambda: _image(preview) != before)
    assert qapp.focusWidget() is fit
    assert main.values()["density"] == "compact"
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


def test_quick_look_changes_draw_once_as_the_last_choice(qapp: QApplication) -> None:
    """Several look changes in a row draw one picture, and it is the last choice. Settings already
    holds that choice, which is what the window saves."""
    page = SettingsPage(None, {}, {}, {})
    page.resize(1024, 640)
    page.show()
    preview = page.style_preview
    _wait(lambda: not preview.stage.pictures[0].source.isNull())
    before = _image(preview)
    box = _child(page, QComboBox, "layoutMain-look")
    shown: list[QImage] = []
    reveal = preview.redraw._show

    def spy(picture: QPixmap) -> None:
        shown.append(picture.toImage())
        reveal(picture)

    preview.redraw._show = spy
    for token in ("preset:high-contrast", "preset:paper", "pack:dark-frost"):
        index = box.findData(token)
        assert index >= 0, token
        box.setCurrentIndex(index)
        for _ in range(4):
            qapp.processEvents()
    assert page.layout_choice()["options"]["classic"]["look"] == "pack:dark-frost"
    assert shown == []
    assert _image(preview) == before
    _wait(lambda: len(shown) == 1)
    assert shown == [_image(preview)]
    burst = _image(preview)
    assert burst != before
    box.setCurrentIndex(box.findData("preset:high-contrast"))
    _wait(lambda: _image(preview) != burst and len(shown) == 2)
    contrast = _image(preview)
    box.setCurrentIndex(box.findData("pack:dark-frost"))
    _wait(lambda: _image(preview) != contrast and len(shown) == 3)
    assert _image(preview) == burst
    assert contrast != burst
    page.close()


def _classic_as_settings_applies_it(pack: str, look: dict, accent: str) -> QImage:
    """The week Settings would show for this pack, look and accent, drawn without the preview."""
    from desktop.native.hours.classic import ClassicWeek
    from desktop.native.hours.hand import Hand, Verdict
    from desktop.native.look import design_look, pack_stylesheet
    from desktop.native.previews import CANVAS, SAMPLE_DAY, SAMPLE_MINUTE, sample_week, system_dark
    from desktop.native.weekmodel import build_week

    dark = system_dark()
    palette, applied = design_look("your", pack, dark, look, accent)
    host = QWidget()
    week = ClassicWeek(Hand(lambda _block, _day, _span: Verdict(False, ""), host))
    week.setStyleSheet(pack_stylesheet(pack, dark, applied, accent, palette))
    week.set_look(applied, palette)
    monday, blocks, homework = sample_week()
    week.set_week(build_week(monday, blocks, homework, None), SAMPLE_DAY, SAMPLE_MINUTE)
    week.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    week.resize(CANVAS)
    week.show()
    QTest.qWait(100)
    picture = week.grab().scaledToWidth(CANVAS.width(), Qt.TransformationMode.SmoothTransformation)
    image = picture.toImage()
    week.close()
    week.deleteLater()
    host.deleteLater()
    QApplication.sendPostedEvents(None, 0)
    return image


def test_the_preview_uses_the_accent_settings_applies(qapp: QApplication) -> None:
    """Choosing Sky changes the preview to the same picture the applied look draws."""
    page = SettingsPage(None, {}, {}, {})
    page.resize(1024, 640)
    page.show()
    preview = page.style_preview
    _wait(lambda: not preview.stage.pictures[0].source.isNull())
    pack = page._pack
    look = page.look_choice()
    before = _image(preview)
    assert before == _classic_as_settings_applies_it(pack, look, "default")
    page.accent.setCurrentIndex(page.accent.findData("sky"))
    assert page.updates()["accent"] == "sky"
    for _ in range(4):
        qapp.processEvents()
    assert _image(preview) == before
    _wait(lambda: _image(preview) != before)
    assert _image(preview) == _classic_as_settings_applies_it(pack, look, "sky")
    page.close()


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
