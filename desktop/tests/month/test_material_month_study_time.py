"""Material Month's "Show study time per date": a date is filled from the bottom, full at the cap, for
what is planned and, deeper, for what is done. The colours and contrasts are checked in the pictures
(pictures/_month_g03.py); these check what is drawn at all and how much of the date it covers."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickView  # noqa: E402

from desktop.native.material.theme import scheme, theme_object  # noqa: E402

QML_DIR = Path(__file__).resolve().parents[2] / "native" / "material" / "qml"
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

CHIP_LIST = [
    {"text": "8:00 AM School", "kind": "plain"},
    {"text": "Due Essay", "kind": "due"},
    {"text": "Due Lab", "kind": "due"},
]


@pytest.fixture(scope="module")
def qapp() -> Iterator[QGuiApplication]:
    yield QGuiApplication.instance() or QGuiApplication(["test-material-month-study"])


@pytest.fixture()
def draw(qapp: QGuiApplication) -> Iterator[object]:
    """Draws one date with the given study shares and hands back its item; every view is hidden when
    the test ends."""
    made: list[QQuickView] = []

    def _draw(planned: float, done: float, study: bool = True, **more: object) -> QQuickItem:
        theme = theme_object(scheme("Slate", "light", "std"), "comfortable", False, False)
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
        # The component and its root live as long as the view: Python would otherwise free them on return.
        _HELD[view] = (component, root)
        made.append(view)
        return root.findChild(QQuickItem, "cell")

    yield _draw
    for view in made:
        view.hide()
        view.deleteLater()


def _all(item: QQuickItem) -> list[QQuickItem]:
    found: list[QQuickItem] = []
    for child in item.childItems():
        found.append(child)
        found.extend(_all(child))
    return found


def test_study_time_fills_the_date_from_the_bottom(draw) -> None:
    cell = draw(planned=0.5, done=0.25)
    planned_item = cell.findChild(QQuickItem, "monthStudyPlanned")
    done_item = cell.findChild(QQuickItem, "monthStudyDone")
    assert planned_item.height() == pytest.approx(HEIGHT * 0.5, abs=1)
    assert done_item.height() == pytest.approx(HEIGHT * 0.25, abs=1)
    assert planned_item.mapToItem(cell, 0, planned_item.height()).y() == pytest.approx(HEIGHT, abs=1)


def test_the_day_number_is_still_shown_on_a_full_date(draw) -> None:
    cell = draw(planned=1.0, done=1.0)
    number = cell.findChild(QQuickItem, "monthDayNumber")
    assert number.isVisible() and number.opacity() == 1


@pytest.mark.parametrize(("study", "planned"), [(False, 0.8), (True, 0.0)])
def test_the_switch_off_or_no_time_draws_no_fill(draw, study: bool, planned: float) -> None:
    cell = draw(planned=planned, done=0.0, study=study)
    assert cell.findChild(QQuickItem, "monthStudyFill").isVisible() is False


@pytest.mark.parametrize("tall", [False, True])
def test_and_n_more_is_shown_once_on_done_time(draw, tall: bool) -> None:
    # A short date says "and N more" beside the number; a taller one says it under its chips.
    height = 120 if tall else 64
    extra = [{"text": "A", "kind": "plain"}, {"text": "B", "kind": "plain"}] if tall else []
    cell = draw(planned=1.0, done=1.0, chips=json.dumps(CHIP_LIST + extra), cellHeight=height)
    more = [
        item
        for item in _all(cell)
        if str(item.objectName()) == "monthMore" and item.isVisible() and float(item.opacity()) > 0
    ]
    assert len(more) == 1, [str(item.property("text")) for item in more]


def test_narrow_dots_sit_on_a_backing_over_study_time(draw) -> None:
    cell = draw(planned=1.0, done=1.0, chips=json.dumps(CHIP_LIST), narrowCell=True)
    assert cell.findChild(QQuickItem, "monthDotsBacking").isVisible()


@pytest.mark.parametrize("name", ["contrastHigh", "picked"])
def test_high_contrast_and_a_picked_date_draw_their_edge_again_over_study_time(draw, name: str) -> None:
    plain = draw(planned=1.0, done=0.0)
    assert plain.findChild(QQuickItem, "monthStudyEdge").isVisible() is False
    marked = draw(planned=1.0, done=0.0, **{name: True})
    assert marked.findChild(QQuickItem, "monthStudyEdge").isVisible() is True
