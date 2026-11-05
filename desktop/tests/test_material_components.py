"""The shared Material 3 controls, at the sizes in the mock-up.

Numbers come from the mock-up's stylesheet and from Jonathan's spec: the rail is 80, the pill is
56 by 32, the bar is 80, a FAB is 56 with radius 6, a segmented button is 40 with an 18px check,
a switch is 52 by 32 and its thumb grows from 16 to 24, a swatch disc is 48 with a 22 badge,
settings type is 16/500 and 14 with padding 16 or 10, an event block is radius 12, a dialog is
radius 8, and a snackbar sits 24px up. A disabled button is on-surface at 12% and 38%, and a
disabled text button has no fill. Space toggles a switch. Right moves the segmented button.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QAccessible, QColor, QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlProperty
    from PySide6.QtQuick import QQuickItem, QQuickView
    from PySide6.QtTest import QTest
    from shiboken6 import delete, isValid

ROOT = Path(__file__).resolve().parents[2]
QML = ROOT / "desktop" / "native" / "material" / "qml"


def _walk(item: QQuickItem) -> Iterator[QQuickItem]:
    yield item
    for child in item.childItems():
        yield from _walk(child)


def _find(item: QQuickItem, name: str) -> QQuickItem:
    for node in _walk(item):
        if node.objectName() == name:
            return node
    raise AssertionError(f"{name} is not in the gallery")


def _child(item: QQuickItem, name: str) -> QQuickItem:
    # The caller keeps `item`. A temporary parent is collected, and shiboken then deletes the child.
    found = item.findChild(QQuickItem, name)
    assert found is not None and isValid(found), name
    return found


def _color(item: QQuickItem, name: str) -> QColor:
    return QColor(_child(item, name).property("color"))


def _press(view: QQuickView, item: QQuickItem, key: Qt.Key) -> None:
    # forceActiveFocus returns None. The key goes to the window only after it is the active focus item.
    view.requestActivate()
    item.forceActiveFocus()
    QGuiApplication.processEvents()
    assert item.hasActiveFocus()
    QTest.keyClick(view, key)
    QGuiApplication.processEvents()


@pytest.fixture(scope="module")
def qapp() -> Iterator[QGuiApplication]:
    yield QGuiApplication.instance() or QGuiApplication(["flexweek-material-components"])


@pytest.fixture
def gallery(qapp: QGuiApplication) -> Iterator[tuple[QQuickView, QQuickItem]]:
    view = QQuickView()
    view.engine().addImportPath(str(QML))
    component = QQmlComponent(view.engine())
    component.setData(b"import components 1.0\nGallery { reduceMotion: true }\n", QUrl())
    assert component.status() == QQmlComponent.Ready, component.errorString()
    root = component.create()
    assert root is not None, component.errorString()
    view.setContent(QUrl(), component, root)
    view.show()
    qapp.processEvents()
    try:
        yield view, root
    finally:
        # The view does not own the gallery item. Closing it leaves both in a cycle, and the suite
        # fails a test that still has a window when the collector runs.
        view.hide()
        view.setSource(QUrl())
        qapp.processEvents()
        if isValid(root):
            delete(root)
        if isValid(view):
            delete(view)
        qapp.processEvents()


def test_fab_is_56_with_radius_16(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """A FAB is 56 by 56, radius 6, filled with the card color (#ffffff)."""
    _view, root = gallery
    fab = _find(root, "fabMeasure")
    shape = _child(fab, "shape")
    assert (fab.width(), fab.height()) == (56, 56)
    assert shape.property("radius") == 6
    assert _color(fab, "shape").name() == "#ffffff"


def test_rail_is_80_and_the_pill_is_56_by_32(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """The rail is 80 wide and the selected destination's indicator is 56 by 32."""
    _view, root = gallery
    rail = _find(root, "railMeasure")
    indicator = _find(_find(root, "destMeasure"), "indicator")
    assert rail.width() == 80
    assert (indicator.width(), indicator.height()) == (56, 32)


def test_bar_is_80_tall(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """The phone navigation bar is 80 tall."""
    _view, root = gallery
    assert _find(root, "barMeasure").height() == 80


def test_segmented_button_is_40_tall_with_an_18_check(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """A segmented button is 40 tall, radius 6, and the active segment's check is 18."""
    _view, root = gallery
    segmented = _find(root, "segmentMeasure")
    shape = _child(segmented, "shape")
    check = _find(segmented, "segmentCheck")
    assert segmented.height() == 40
    assert shape.property("radius") == 6
    assert (check.width(), check.height()) == (18, 18)
    assert check.isVisible()


def test_arrow_keys_move_the_segmented_button(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """Right arrow leaves Comfortable and selects Compact."""
    view, root = gallery
    segmented = _find(root, "segmentMeasure")
    assert segmented.property("current") == "comfortable"
    _press(view, segmented, Qt.Key.Key_Right)
    assert segmented.property("current") == "compact"


def test_switch_is_52_by_32_and_the_thumb_grows_from_16_to_24(
    gallery: tuple[QQuickView, QQuickItem],
) -> None:
    """A switch is 52 by 32. Off, the thumb is 16 at (8, 8). On, it is 24 at (24, 4)."""
    view, root = gallery
    switch = _find(root, "switchMeasure")
    thumb = _child(switch, "switchThumb")
    assert (switch.width(), switch.height()) == (52, 32)
    assert (thumb.width(), thumb.height(), thumb.x(), thumb.y()) == (16, 16, 8, 8)
    _press(view, switch, Qt.Key.Key_Space)
    assert switch.property("checked") is True
    assert (thumb.width(), thumb.height(), thumb.x(), thumb.y()) == (24, 24, 24, 4)


def test_swatch_disc_is_48_and_the_badge_is_22(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """A preset swatch's disc is 48 and the selected check badge is 22."""
    _view, root = gallery
    swatch = _find(root, "swatchMeasure")
    disc = _child(swatch, "swatchDisc")
    badge = _child(swatch, "swatchBadge")
    assert (disc.width(), disc.height()) == (48, 48)
    assert (badge.width(), badge.height()) == (22, 22)
    assert badge.property("radius") == 11
    assert badge.isVisible()


def test_settings_row_type_and_padding(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """A settings group has radius 8. The title is 16/500 at the 16px padding, the subtitle 14."""
    _view, root = gallery
    group = _find(root, "groupMeasure")
    shape = _child(group, "shape")
    row = _find(root, "rowMeasure")
    title = _child(row, "title")
    subtitle = _child(row, "subtitle")
    assert shape.property("radius") == 8
    assert title.y() == 16
    assert (title.property("font").pixelSize(), title.property("font").weight()) == (16, 500)
    assert (subtitle.property("font").pixelSize(), subtitle.property("font").weight()) == (14, 400)


def test_compact_settings_row_padding_is_10(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """Compact density changes the settings row's vertical padding from 16 to 10."""
    _view, root = gallery
    row = _find(root, "compactRow")
    title = _child(row, "title")
    assert title.y() == 10


def test_event_block_school_colour_radius_and_two_lines(
    gallery: tuple[QQuickView, QQuickItem],
) -> None:
    """A school block is #e4ebf7, radius 6, padded 6 by 8 past the 4px bar, and the title is two lines."""
    _view, root = gallery
    block = _find(root, "eventMeasure")
    shape = _child(block, "shape")
    title = _child(block, "title")
    body = _child(block, "body")
    bar = _child(block, "bar")
    assert QColor(shape.property("color")).name() == "#e4ebf7"
    assert shape.property("radius") == 6
    assert bar.width() == 4
    assert (body.x(), body.y()) == (12, 6)
    assert title.property("maximumLineCount") == 2
    assert title.property("lineCount") == 2
    assert (title.property("font").pixelSize(), title.property("font").weight()) == (12, 600)


def test_past_event_is_dimmed(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """A past event block fades its fill and bar to 55% while the block and title keep full opacity."""
    _view, root = gallery
    block = _find(root, "pastEvent")
    shape = _child(block, "shape")
    bar = _child(block, "bar")
    title = _child(block, "title")
    assert block.opacity() == pytest.approx(1.0)
    assert shape.property("opacity") == pytest.approx(0.55)
    assert bar.property("opacity") == pytest.approx(0.55)
    assert title.property("opacity") == pytest.approx(1.0)


def test_dialog_card_is_440_with_radius_28(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """A dialog card is 440 wide and radius 8."""
    _view, root = gallery
    dialog = _find(root, "dialogMeasure")
    card = _child(dialog, "dialogCard")
    assert card.width() == 440
    assert card.property("radius") == 8


def test_snackbar_sits_24_from_the_bottom(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """A snackbar is 48 tall and its top is 24px plus its height short of the host's bottom."""
    _view, root = gallery
    host = _find(root, "snackHost")
    snack = _find(root, "snackMeasure")
    assert snack.height() == 48
    assert snack.y() == host.height() - 24 - snack.height()


def test_mini_month_opens_on_monday_the_26th(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """November 2026 starts on Sunday, so the Monday-first grid opens on 26 and today is a 28 disc."""
    _view, root = gallery
    month = _find(root, "monthMeasure")
    today = _find(month, "todayDisc")
    assert _find(month, "cell0").property("text") == "26"
    assert _find(month, "cell6").property("text") == "1"
    assert (today.width(), today.height()) == (28, 28)


def test_mini_month_shows_the_keyboard_cursor(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """Tabbing onto the month shows a ring on the cursor, and arrows move it before Enter picks the day."""
    view, root = gallery
    month = _find(root, "monthMeasure")
    heard: list[int] = []
    month.dayActivated.connect(lambda day: heard.append(int(day)))
    with pytest.raises(AssertionError, match="cursorRing"):
        _find(month, "cursorRing")
    _press(view, month, Qt.Key_Right)
    assert month.property("cursor") == 6
    ring = _find(month, "cursorRing")
    assert ring.isVisible() is True
    cell = _find(month, "cell10")
    iface = QAccessible.queryAccessibleInterface(cell)
    assert iface is not None
    assert iface.text(QAccessible.Text.Name) == "5"
    _press(view, month, Qt.Key_Return)
    assert heard == [6]


def test_disabled_filled_button_uses_the_spec_alphas(
    gallery: tuple[QQuickView, QQuickItem],
) -> None:
    """A disabled filled button's fill is on-surface at 12% and its label is on-surface at 38%."""
    _view, root = gallery
    button = _find(root, "disabledMeasure")
    fill = _color(button, "shape")
    ink = _color(button, "label")
    on_surface = QColor("#0f172a")
    assert fill.name() == on_surface.name()
    assert fill.alphaF() == pytest.approx(0.12, abs=0.02)
    assert ink.name() == on_surface.name()
    assert ink.alphaF() == pytest.approx(0.38, abs=0.02)


def test_disabled_text_button_has_no_fill(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """A disabled text button keeps a clear fill and on-surface ink at 38%."""
    _view, root = gallery
    button = _find(root, "textDisabledMeasure")
    assert _color(button, "shape").alphaF() == 0
    assert _color(button, "label").alphaF() == pytest.approx(0.38, abs=0.02)


def test_enabled_filled_button_uses_primary(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """An enabled filled button is 40 tall and filled with Slate's primary, #3d6fc4."""
    _view, root = gallery
    button = _find(root, "filledMeasure")
    assert button.height() == 40
    assert _color(button, "shape").name() == "#3d6fc4"


def test_high_contrast_outlined_stroke_is_one_and_a_half(
    gallery: tuple[QQuickView, QQuickItem],
) -> None:
    """High contrast thickens an outlined button's stroke from 1 to 1.5."""
    _view, root = gallery
    outlined = _find(root, "outlinedMeasure")
    outlined.setProperty("kind", "outlined")
    shape = _child(outlined, "shape")
    assert QQmlProperty(shape, "border.width").read() == 1
    root.setProperty("scheme", "high")
    assert QQmlProperty(shape, "border.width").read() == 1.5
