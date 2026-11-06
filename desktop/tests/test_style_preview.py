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
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QImage, QPixmap
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QRadioButton, QScrollArea, QWidget

    from desktop.native.layouts.dialog import LayoutSection
    from desktop.native.settings import LOOK_TILE, SettingsPage
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


def test_the_look_preview_takes_a_real_share_of_a_large_window(qapp: QApplication) -> None:
    """A wide window gives the preview about 40% of the stage, so Fit fills the room instead of
    squeezing the window picture into a thin strip between empty bars."""
    page = SettingsPage(None, {}, {}, {})
    page.resize(1600, 1000)
    page.show()
    preview = page.style_preview
    _wait(lambda: preview.isVisible() and not preview.stage.pictures[0].source.isNull())
    for _ in range(4):
        qapp.processEvents()
    stage = preview.parentWidget()
    assert stage is not None
    assert preview.height() >= stage.height() * 0.35
    shown = _child(preview, QLabel, "stylePreviewImage").pixmap()
    assert shown is not None and not shown.isNull()
    assert shown.deviceIndependentSize().height() >= 240
    page.close()


def test_the_look_preview_keeps_its_minimum_on_a_small_window(qapp: QApplication) -> None:
    """At the smallest Settings window the preview still holds its 240, and the Look cards keep
    enough room to scroll under it."""
    page = SettingsPage(None, {}, {}, {})
    page.resize(1024, 640)
    page.show()
    preview = page.style_preview
    _wait(lambda: preview.isVisible() and not preview.stage.pictures[0].source.isNull())
    for _ in range(4):
        qapp.processEvents()
    assert preview.height() >= 240
    cards = page.stack.currentWidget()
    assert isinstance(cards, QScrollArea)
    assert cards.height() >= 200
    page.close()


def test_other_settings_pages_do_not_keep_room_for_the_preview(qapp: QApplication) -> None:
    """Another page takes the whole stage: the preview hides and its row hands the space back, so
    the cards start at the top."""
    page = SettingsPage(None, {}, {}, {})
    page.resize(1600, 1000)
    page.show()
    preview = page.style_preview
    _wait(lambda: preview.isVisible() and not preview.stage.pictures[0].source.isNull())
    stage = preview.parentWidget()
    assert stage is not None
    page.nav.setCurrentRow(1)
    for _ in range(4):
        qapp.processEvents()
    assert preview.isVisible() is False
    cards = page.stack.currentWidget()
    assert isinstance(cards, QScrollArea)
    assert cards.mapTo(stage, cards.rect().topLeft()).y() == 0
    page.close()


def _open_look(qapp: QApplication, width: int, height: int) -> SettingsPage:
    page = SettingsPage(None, {}, {}, {})
    page.resize(width, height)
    page.show()
    preview = page.style_preview
    _wait(lambda: preview.isVisible() and not preview.stage.pictures[0].source.isNull())
    for _ in range(6):
        qapp.processEvents()
    return page


def test_a_wide_look_page_puts_the_preview_beside_the_cards(qapp: QApplication) -> None:
    """At 1400 the preview sits on the right of the Look cards, about 60% of the stage, and Fit
    fills that column's width instead of the strip's ~370 px picture."""
    page = _open_look(qapp, 1400, 900)
    preview = page.style_preview
    stage = preview.parentWidget()
    stack = page.stack
    footer = page.footer
    assert stage is not None
    preview_origin = preview.mapTo(stage, preview.rect().topLeft())
    stack_corner = stack.mapTo(stage, stack.rect().topRight())
    assert preview_origin.x() >= stack_corner.x()
    assert 0.55 * stage.width() <= preview.width() <= 0.65 * stage.width()
    preview_bottom = preview.mapTo(stage, preview.rect().bottomLeft()).y()
    footer_top = footer.mapTo(stage, footer.rect().topLeft()).y()
    assert preview_bottom <= footer_top
    shown = preview.stage.stack.currentWidget().widget().pixmap()
    assert shown is not None and not shown.isNull()
    assert shown.deviceIndependentSize().width() > 500
    page.close()


def test_the_left_look_column_fits_two_tiles_when_just_wide_enough(qapp: QApplication) -> None:
    """Between 1000 and 1100 px the Look cards stay wide enough for two tiles on the first row."""
    page = _open_look(qapp, 1050, 800)
    first, second = page.look.more.cards[0], page.look.more.cards[1]
    grid = page.look.more
    assert first.mapTo(grid, first.rect().topLeft()).y() == second.mapTo(grid, second.rect().topLeft()).y()
    page.close()


def test_a_narrow_look_page_keeps_the_preview_strip_on_top(qapp: QApplication) -> None:
    """Below the 1000 px threshold the preview stays the J20 strip: above the cards, full stage width."""
    page = _open_look(qapp, 900, 700)
    preview = page.style_preview
    stage = preview.parentWidget()
    stack = page.stack
    assert stage is not None
    preview_origin = preview.mapTo(stage, preview.rect().topLeft())
    stack_origin = stack.mapTo(stage, stack.rect().topLeft())
    assert preview_origin.y() < stack_origin.y()
    assert preview.width() == stage.width()
    assert stack.width() == stage.width()
    page.close()


def test_resizing_across_the_side_by_side_threshold_switches_layout(qapp: QApplication) -> None:
    """Crossing 1000 px wide switches between side-by-side and the strip without reopening Settings."""
    page = _open_look(qapp, 1400, 900)
    preview = page.style_preview
    stage = preview.parentWidget()
    stack = page.stack
    assert stage is not None
    preview_left = preview.mapTo(stage, preview.rect().topLeft()).x()
    stack_right = stack.mapTo(stage, stack.rect().topRight()).x()
    assert preview_left >= stack_right
    page.resize(900, 700)
    for _ in range(8):
        qapp.processEvents()
    assert preview.mapTo(stage, preview.rect().topLeft()).y() < stack.mapTo(stage, stack.rect().topLeft()).y()
    assert preview.width() == stage.width()
    page.resize(1400, 900)
    for _ in range(8):
        qapp.processEvents()
    preview_left = preview.mapTo(stage, preview.rect().topLeft()).x()
    stack_right = stack.mapTo(stage, stack.rect().topRight()).x()
    assert preview_left >= stack_right
    assert 0.55 * stage.width() <= preview.width() <= 0.65 * stage.width()
    page.close()


def test_another_section_at_a_wide_width_gives_the_cards_the_whole_stage(qapp: QApplication) -> None:
    """Planning at 1400 has no preview and no leftover column: the cards use the full stage."""
    page = _open_look(qapp, 1400, 900)
    preview = page.style_preview
    stage = preview.parentWidget()
    assert stage is not None
    page.nav.setCurrentRow(1)
    for _ in range(6):
        qapp.processEvents()
    assert preview.isVisible() is False
    assert page.stack.width() == stage.width()
    page.close()


def test_scrolling_the_look_cards_does_not_move_the_preview(qapp: QApplication) -> None:
    """The preview stays put while the Look cards scroll."""
    page = _open_look(qapp, 1400, 900)
    preview = page.style_preview
    area = page.stack.currentWidget()
    assert isinstance(area, QScrollArea)
    before = preview.geometry()
    bar = area.verticalScrollBar()
    assert bar.maximum() > 0
    bar.setValue(bar.maximum())
    for _ in range(4):
        qapp.processEvents()
    assert preview.geometry() == before
    page.close()


def _wear_large_text(qapp: QApplication, page: SettingsPage) -> None:
    text = page.knobs["text"]
    text.setCurrentIndex(text.findData("large"))
    for _ in range(8):
        qapp.processEvents()


@pytest.mark.parametrize("width", [1050, 1280])
def test_large_text_keeps_two_look_tiles_on_a_row(qapp: QApplication, width: int) -> None:
    """Large text widens the Look tiles; the cards column still holds two of them, beside the
    preview or, when that no longer fits, under the strip."""
    page = _open_look(qapp, width, 800)
    _wear_large_text(qapp, page)
    assert page.look.tile_width > LOOK_TILE
    grid = page.look.more
    first, second = grid.cards[0], grid.cards[1]
    assert first.mapTo(grid, first.rect().topLeft()).y() == second.mapTo(grid, second.rect().topLeft()).y()
    page.close()


@pytest.mark.parametrize("width", [1000, 1050, 1280, 1400])
@pytest.mark.parametrize("large", [False, True])
def test_the_preview_controls_are_never_squeezed(qapp: QApplication, width: int, large: bool) -> None:
    page = _open_look(qapp, width, 800)
    if large:
        _wear_large_text(qapp, page)
    for name in ("stylePreviewSurface", "stylePreviewSize"):
        control = page.style_preview.findChild(QWidget, name)
        assert control is not None and control.isVisible(), name
        assert control.width() >= control.minimumSizeHint().width(), (name, width, large)
    page.close()


@pytest.mark.parametrize("size", [(1400, 900), (1280, 800)])
def test_the_side_preview_controls_follow_the_picture(qapp: QApplication, size: tuple[int, int]) -> None:
    """Side by side with Fit, the controls sit right under the fitted picture, not at the bottom
    of the column; Actual size gives the preview the whole height back to scroll in."""
    page = _open_look(qapp, *size)
    preview = page.style_preview
    stage_box = page.stage.geometry()
    assert preview.geometry().left() >= page.stack.geometry().right(), "side by side"
    # The picture on the page showing; the Day screen page holds a label of the same name.
    image = preview.stage.stack.currentWidget().widget()
    bar = preview.findChild(QWidget, "stylePreviewBar")
    picture_bottom = image.mapTo(page, image.rect().bottomLeft()).y()
    bar_top = bar.mapTo(page, bar.rect().topLeft()).y()
    assert 0 <= bar_top - picture_bottom <= 16, (picture_bottom, bar_top)
    preview.stage.zoom.setCurrentIndex(1)
    for _ in range(8):
        qapp.processEvents()
    assert preview.height() >= stage_box.height() * 0.7
    page.close()


def test_side_by_side_waits_until_the_preview_controls_fit(qapp: QApplication) -> None:
    """Side by side needs room for the cards and the preview's own controls; when the controls
    would be squeezed, the strip keeps them whole."""
    page = _open_look(qapp, 1050, 800)
    assert page._stage_mode == "side"
    wide = QSize(page.stage.width(), 0)
    page.style_preview.minimumSizeHint = lambda: wide  # type: ignore[method-assign]
    page._show_preview_row(0)
    for _ in range(6):
        qapp.processEvents()
    assert page._stage_mode == "strip"
    assert page.style_preview.geometry().bottom() <= page.stack.geometry().top()
    page.close()
