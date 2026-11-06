"""J23: Material Month's "Show study time per date" fills each date from the bottom, full at the cap,
with the homework tint for what is planned and a deeper homework colour for what is done."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickView  # noqa: E402

from desktop.native.material.theme import scheme, theme_object  # noqa: E402
from desktop.native.tokens import contrast  # noqa: E402

QML_DIR = Path(__file__).resolve().parents[1] / "native" / "material" / "qml"
WIDTH, HEIGHT = 160, 120
_HELD: dict[QQuickView, tuple[QQmlComponent, object]] = {}
SOURCE = """
import QtQuick
import month 1.0

Rectangle {
    width: 200
    height: 160
    color: "#808080"
    property var theme
    property bool study: true
    property real planned: 0
    property real done: 0
    property bool picked: false
    property bool contrastHigh: false
    property bool narrowCell: false
    property string chips: "[]"
    property int cellHeight: HEIGHT
    MonthCell {
        objectName: "cell"
        x: 20
        y: 20
        width: WIDTH
        height: parent.cellHeight
        picked: parent.picked
        highContrast: parent.contrastHigh
        narrow: parent.narrowCell
        chipsJson: parent.chips
        theme: parent.theme
        day: 12
        reduceMotion: true
        showStudy: parent.study
        plannedShare: parent.planned
        completedShare: parent.done
    }
}
""".replace("WIDTH", str(WIDTH)).replace("HEIGHT", str(HEIGHT))


@pytest.fixture(scope="module")
def qapp() -> Iterator[QGuiApplication]:
    yield QGuiApplication.instance() or QGuiApplication(["test-j23"])


def _draw(qapp: QGuiApplication, mode: str, planned: float, done: float, study: bool = True, **more: object):
    theme = theme_object(scheme("Slate", mode, "std"), "comfortable", False, False)
    view = QQuickView()
    view.engine().addImportPath(str(QML_DIR))
    view.resize(200, 160)
    component = QQmlComponent(view.engine())
    component.setData(SOURCE.encode("utf-8"), view.engine().baseUrl())
    root = component.create()
    assert root is not None, component.errorString()
    root.setProperty("theme", theme)
    root.setProperty("planned", planned)
    root.setProperty("done", done)
    root.setProperty("study", study)
    for name, value in more.items():
        root.setProperty(name, value)
    view.setContent(QUrl(), component, root)
    view.show()
    for _ in range(5):
        qapp.processEvents()
    image = view.grabWindow()
    # The component and its root live as long as the view: Python would otherwise free them on return.
    _HELD[view] = (component, root)
    cell = root.findChild(QQuickItem, "cell")
    return view, cell, image, theme


def _at(image: QImage, x: float, y: float) -> str:
    """The colour drawn at a point in the cell, the cell's top left being (20, 20) in the view."""
    return image.pixelColor(int(20 + x), int(20 + y)).name()


def _near(found: str, wanted: str, slack: int = 3) -> bool:
    a, b = QColor(found), QColor(wanted)
    pairs = ((a.red(), b.red()), (a.green(), b.green()), (a.blue(), b.blue()))
    return all(abs(x - y) <= slack for x, y in pairs)


def _distance(a: str, b: str) -> int:
    one, two = QColor(a), QColor(b)
    return abs(one.red() - two.red()) + abs(one.green() - two.green()) + abs(one.blue() - two.blue())


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_study_time_fills_the_date_from_the_bottom(qapp: QGuiApplication, mode: str) -> None:
    view, cell, image, theme = _draw(qapp, mode, planned=0.5, done=0.25)
    try:
        homework = theme["classes"]["assignments"]
        middle = WIDTH / 2
        # Above half the height: no study time, the date's own colour.
        empty = _at(image, middle, HEIGHT * 0.4)
        assert _near(empty, theme["surfaceContainerLow"]), (empty, theme["surfaceContainerLow"])
        # Between half and three quarters down: planned only, the homework tint.
        planned = _at(image, middle, HEIGHT * 0.62)
        assert _near(planned, homework["fill"]), (planned, homework["fill"])
        # The bottom quarter: done, deeper toward the homework colour than planned is.
        done = _at(image, middle, HEIGHT - 6)
        assert _distance(done, homework["bar"]) + 30 < _distance(planned, homework["bar"]), (done, planned)
        planned_item = cell.findChild(QQuickItem, "monthStudyPlanned")
        done_item = cell.findChild(QQuickItem, "monthStudyDone")
        assert planned_item.height() == pytest.approx(HEIGHT * 0.5, abs=1)
        assert done_item.height() == pytest.approx(HEIGHT * 0.25, abs=1)
        assert planned_item.mapToItem(cell, 0, planned_item.height()).y() == pytest.approx(HEIGHT, abs=1)
    finally:
        view.hide()
        view.deleteLater()


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_day_number_stays_readable_on_a_full_date(qapp: QGuiApplication, mode: str) -> None:
    view, _cell, image, theme = _draw(qapp, mode, planned=1.0, done=1.0)
    try:
        # Beside the number, where nothing but the fill is drawn.
        under = _at(image, WIDTH - 12, 14)
        assert _distance(under, theme["surfaceContainerLow"]) > 30, under
        number = _cell.findChild(QQuickItem, "monthDayNumber")
        assert number.isVisible() and number.opacity() == 1
        ink = QColor(number.property("color")).name()
        assert contrast(ink, under) >= 4.5, (ink, under)
    finally:
        view.hide()
        view.deleteLater()


def test_the_switch_off_or_no_time_draws_no_fill(qapp: QGuiApplication) -> None:
    for study, planned in ((False, 0.8), (True, 0.0)):
        view, cell, image, theme = _draw(qapp, "light", planned=planned, done=0.0, study=study)
        try:
            assert cell.findChild(QQuickItem, "monthStudyFill").isVisible() is False
            bottom = _at(image, WIDTH / 2, HEIGHT - 6)
            assert _near(bottom, theme["surfaceContainerLow"]), bottom
        finally:
            view.hide()
            view.deleteLater()


CHIP_LIST = [
    {"text": "8:00 AM School", "kind": "plain"},
    {"text": "Due Essay", "kind": "due"},
    {"text": "Due Lab", "kind": "due"},
]
CHIPS = json.dumps(CHIP_LIST)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_high_contrast_keeps_its_edge_over_study_time(qapp: QGuiApplication, mode: str) -> None:
    edges = {}
    for high in (False, True):
        view, _cell, image, theme = _draw(qapp, mode, planned=1.0, done=0.0, contrastHigh=high)
        try:
            edges[high] = _at(image, 0, HEIGHT / 2)
        finally:
            view.hide()
            view.deleteLater()
    fill = theme["classes"]["assignments"]["fill"]
    # Without High contrast the side of the date is the fill; with it, the outline is drawn over the fill.
    assert _distance(edges[True], theme["outline"]) < _distance(edges[False], theme["outline"]) - 20, edges
    assert _distance(edges[True], fill) > 20, (edges, fill)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_a_picked_date_full_of_study_time_still_looks_picked(qapp: QGuiApplication, mode: str) -> None:
    sides = {}
    for picked in (False, True):
        view, _cell, image, _theme = _draw(qapp, mode, planned=1.0, done=1.0, picked=picked)
        try:
            sides[picked] = (_at(image, 1, HEIGHT / 2), _at(image, WIDTH / 2, HEIGHT - 1))
        finally:
            view.hide()
            view.deleteLater()
    assert _distance(sides[True][0], sides[False][0]) > 30, sides
    assert _distance(sides[True][1], sides[False][1]) > 30, sides


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("tall", [False, True])
def test_and_n_more_is_readable_on_done_time(qapp: QGuiApplication, mode: str, tall: bool) -> None:
    # A short date says "and N more" beside the number; a taller one says it under its chips.
    height = 120 if tall else 64
    extra = [{"text": "A", "kind": "plain"}, {"text": "B", "kind": "plain"}] if tall else []
    chips = json.dumps(CHIP_LIST + extra)
    view, cell, image, _theme = _draw(qapp, mode, planned=1.0, done=1.0, chips=chips, cellHeight=height)
    try:
        more = [
            item
            for item in _all(cell)
            if str(item.objectName()) == "monthMore" and item.isVisible() and float(item.opacity()) > 0
        ]
        assert len(more) == 1, [str(item.property("text")) for item in more]
        ink = QColor(more[0].property("color")).name()
        under = _at(image, WIDTH - 4, height / 2)
        assert contrast(ink, under) >= 4.5, (ink, under)
    finally:
        view.hide()
        view.deleteLater()


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_narrow_dots_sit_on_a_backing_over_study_time(qapp: QGuiApplication, mode: str) -> None:
    view, cell, image, theme = _draw(qapp, mode, planned=1.0, done=1.0, chips=CHIPS, narrowCell=True)
    try:
        backing = cell.findChild(QQuickItem, "monthDotsBacking")
        assert backing.isVisible()
        corner = backing.mapToItem(cell, 2, backing.height() / 2)
        around = _at(image, corner.x(), corner.y())
        homework = theme["classes"]["assignments"]["bar"]
        assert contrast(homework, around) >= 3, (homework, around)
    finally:
        view.hide()
        view.deleteLater()


def _all(item: QQuickItem) -> list[QQuickItem]:
    found: list[QQuickItem] = []
    for child in item.childItems():
        found.append(child)
        found.extend(_all(child))
    return found
