"""J23: Material Month's "Show study time per date" fills each date from the bottom, full at the cap,
with the homework tint for what is planned and a deeper homework colour for what is done."""

from __future__ import annotations

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
    MonthCell {
        objectName: "cell"
        x: 20
        y: 20
        width: WIDTH
        height: HEIGHT
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


def _draw(qapp: QGuiApplication, mode: str, planned: float, done: float, study: bool = True):
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
        assert contrast(theme["onSurface"], under) >= 4.5, (theme["onSurface"], under)
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
