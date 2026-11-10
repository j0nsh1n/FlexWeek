"""The style picker draws the real view while a style, an option, or the accent changes, keeps focus
where the student is, and hides on the other Settings pages. Where it sits and how big it is are judged
on the pictures in pictures/screens_settings_h2.py."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QComboBox, QRadioButton, QWidget

from desktop.native.layouts.dialog import LayoutSection
from desktop.native.settings import SettingsPage
from desktop.native.style_preview import ACTUAL_NOTE, Redraw, StylePreview
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

OPEN = {"main": "timeline", "day": "dial", "options": {}}


def sections() -> tuple[LayoutSection, LayoutSection]:
    main = LayoutSection("main", "plan", "Main view", "Plan the week.", OPEN, "system")
    day = LayoutSection("day", "day", "Day screen", "Watch the day.", OPEN, "system")
    return main, day


def preview_of(made: tuple[LayoutSection, LayoutSection]) -> StylePreview:
    main, day = made
    preview = StylePreview([main, day], pack=lambda: "system", look=lambda: None)
    preview.resize(360, 320)
    return preview


def image(preview: StylePreview) -> QImage:
    return preview.stage.pictures[0].source.toImage()


def drawn(preview: StylePreview) -> bool:
    return not preview.stage.pictures[0].source.isNull()


def child[T: QWidget](parent: QWidget, kind: type[T], name: str) -> T:
    found = parent.findChild(kind, name)
    assert found is not None, name
    return found


def test_an_option_change_redraws_after_a_short_delay_and_keeps_focus(qapp: QApplication) -> None:  # noqa: F811
    """Spacing is part of the picture. The draw waits, so a drag is not a draw on every tick, and the
    control the student is on keeps the keyboard."""
    main, _day = made = sections()
    preview = preview_of(made)
    preview.show()
    wait_until(qapp, lambda: drawn(preview))
    before = image(preview)
    compact = child(main, QRadioButton, "layoutMain-density-compact")
    compact.click()
    for _ in range(4):
        qapp.processEvents()
    assert preview.redraw.waiting()
    assert image(preview) == before
    fit = child(preview, QRadioButton, "stylePreviewSize-True")
    fit.setFocus(Qt.FocusReason.TabFocusReason)
    wait_until(qapp, lambda: image(preview) != before)
    assert qapp.focusWidget() is fit
    assert main.values()["density"] == "compact"
    preview.stage.zoom.buttons()[1].click()
    shown = preview.stage.pictures[0].image
    assert shown.width() == preview.stage.pictures[0].source.deviceIndependentSize().width()
    assert preview.stage.note.text() == ACTUAL_NOTE
    day = child(preview, QRadioButton, "stylePreviewSurface-day")
    main_picture = image(preview)
    day.click()
    wait_until(qapp, lambda: image(preview) != main_picture)
    assert preview.stage.surface_id() == "day"
    preview.close()


def test_a_redraw_superseded_while_painting_is_dropped(qapp: QApplication) -> None:  # noqa: F811
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
    wait_until(qapp, lambda: len(shown) >= 1)
    assert held[0].dropped >= 1
    assert [picture.width() for picture in shown] == [8]
    held.clear()
    host.deleteLater()
    qapp.processEvents()


def test_quick_look_changes_draw_once_as_the_last_choice(qapp: QApplication) -> None:  # noqa: F811
    """Several look changes in a row draw one picture, and it is the last choice. Settings already holds
    that choice, which is what the window saves."""
    page = SettingsPage(None, {}, {}, {})
    page.resize(1024, 640)
    page.show()
    preview = page.style_preview
    wait_until(qapp, lambda: drawn(preview))
    before = image(preview)
    box = child(page, QComboBox, "layoutMain-look")
    shown: list[QImage] = []
    reveal = preview.redraw._show

    def spy(picture: QPixmap) -> None:
        shown.append(picture.toImage())
        reveal(picture)

    preview.redraw._show = spy
    # The wait before a draw is real time, and a busy machine takes longer than it to get through the
    # three changes. Held for the burst, then let go, so the test does not race it.
    delay = preview.redraw._timer
    delay.setInterval(60_000)
    for token in ("preset:high-contrast", "preset:paper", "pack:dark-frost"):
        index = box.findData(token)
        assert index >= 0, token
        box.setCurrentIndex(index)
        for _ in range(4):
            qapp.processEvents()
    assert page.layout_choice()["options"]["classic"]["look"] == "pack:dark-frost"
    assert shown == []
    assert image(preview) == before
    delay.setInterval(0)
    delay.start()
    wait_until(qapp, lambda: len(shown) == 1)
    assert shown == [image(preview)]
    burst = image(preview)
    assert burst != before
    box.setCurrentIndex(box.findData("preset:high-contrast"))
    wait_until(qapp, lambda: image(preview) != burst and len(shown) == 2)
    contrast = image(preview)
    box.setCurrentIndex(box.findData("pack:dark-frost"))
    wait_until(qapp, lambda: image(preview) != contrast and len(shown) == 3)
    assert image(preview) == burst
    assert contrast != burst
    page.close()


def test_the_preview_is_named_and_reachable_at_large_text_with_motion_off(qapp: QApplication) -> None:  # noqa: F811
    """1024 by 640, Large text, animations off: the picture is on screen, named, its Fit choice takes
    the keyboard, and it hides on another page and comes back on the Look page."""
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
    wait_until(qapp, lambda: preview.isVisible() and drawn(preview))
    stage = child(preview, QWidget, "stylePreview")
    zoom = child(preview, QWidget, "stylePreviewSize")
    surface = child(preview, QWidget, "stylePreviewSurface")
    assert stage.accessibleName() == "Style preview"
    assert zoom.accessibleName() == "Preview size"
    assert surface.accessibleName() == "Preview"
    fit = child(preview, QRadioButton, "stylePreviewSize-True")
    assert fit.accessibleName() == "Fit"
    assert fit.isVisible()
    fit.setFocus(Qt.FocusReason.TabFocusReason)
    assert qapp.focusWidget() is fit
    page.nav.setCurrentRow(1)
    qapp.processEvents()
    assert preview.isVisible() is False
    page.nav.setCurrentRow(0)
    qapp.processEvents()
    assert preview.isVisible() is True
    page.close()


def open_look(qapp: QApplication, width: int, height: int) -> SettingsPage:  # noqa: F811
    page = SettingsPage(None, {}, {}, {})
    page.resize(width, height)
    page.show()
    preview = page.style_preview
    wait_until(qapp, lambda: preview.isVisible() and drawn(preview))
    for _ in range(6):
        qapp.processEvents()
    return page


def test_another_section_hides_the_preview_at_a_wide_width(qapp: QApplication) -> None:  # noqa: F811
    """Planning at 1400 has no preview."""
    page = open_look(qapp, 1400, 900)
    page.nav.setCurrentRow(1)
    for _ in range(6):
        qapp.processEvents()
    assert page.style_preview.isVisible() is False
    page.close()


def test_crossing_the_side_by_side_width_switches_between_the_side_and_the_strip(
    qapp: QApplication,  # noqa: F811
) -> None:
    """Crossing 1000 px wide switches between side-by-side and the strip without reopening Settings."""
    page = open_look(qapp, 1400, 900)
    assert page._stage_mode == "side"
    page.resize(900, 700)
    wait_until(qapp, lambda: page._stage_mode == "strip")
    page.resize(1400, 900)
    wait_until(qapp, lambda: page._stage_mode == "side")
    page.close()


def test_side_by_side_waits_until_the_preview_controls_fit(qapp: QApplication) -> None:  # noqa: F811
    """Side by side needs room for the cards and the preview's own controls; when the controls would be
    squeezed, the strip keeps them whole."""
    page = open_look(qapp, 1050, 800)
    assert page._stage_mode == "side"
    wide = QSize(page.stage.width(), 0)
    page.style_preview.minimumSizeHint = lambda: wide  # type: ignore[method-assign]
    page._show_preview_row(0)
    for _ in range(6):
        qapp.processEvents()
    assert page._stage_mode == "strip"
    page.close()
