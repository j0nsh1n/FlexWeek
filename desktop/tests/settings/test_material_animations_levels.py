"""Material's Animations (Off / Reduce / Normal / More) and Motion speed (Look > Advanced) change what moves
and for how long, as the Widgets levels did (native/motion_level.py): Off moves and fades nothing, Reduce
keeps the short fades and nothing travels, Normal, More is 2.5 times as slow and travels a third further.

The expected times come from those rules and the component's own Normal duration (a Switch's thumb 300 ms, its
track colour 200 ms, the shell's page fade 300 ms), not from what the code returns now."""

from __future__ import annotations

# ruff: noqa: F811
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickView  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from shiboken6 import delete, isValid  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import material_window, qapp  # noqa: E402, F401
from desktop.tests.material_support import pump, qml, show_material  # noqa: E402

QML = Path(__file__).resolve().parents[2] / "native" / "material" / "qml"

PACE_REACH = {"normal": (1.0, 1.0), "extra": (2.5, 4 / 3), "reduce": (1.0, 0.0), "off": (0.0, 0.0)}
# level -> (page fade ms, Switch thumb travel ms, Switch track colour fade ms)
LEVEL_TIMES = {
    "normal": (300, 300, 200),
    "extra": (750, 750, 500),
    "reduce": (300, 0, 200),
    "off": (0, 0, 0),
}


def _publish(qapp: QApplication, window: NativeWindow, level: str, speed: str = "Normal") -> object:
    bridge = window._material_page.bridge
    window._motion = level
    bridge._advanced = {**bridge._advanced, "motion": speed}
    bridge._publish_theme()
    bridge.changed.emit()
    pump(qapp)
    return bridge


@pytest.fixture
def switch_probe(qapp: QApplication) -> Iterator[object]:
    """A real Switch in an engine of its own, its Motion bound from the probe the way Main.qml binds it."""
    view = QQuickView()
    view.engine().addImportPath(str(QML))
    component = QQmlComponent(view.engine())
    component.setData(
        b"import QtQuick\nimport components 1.0\n"
        b"Item {\n  id: top\n  width: 80; height: 40\n  property real pace: 1\n  property real reach: 1\n"
        b"  Binding { target: Motion; property: 'pace'; value: top.pace }\n"
        b"  Binding { target: Motion; property: 'reach'; value: top.reach }\n"
        b"  Switch { id: sw; objectName: 'sw'; theme: ({}) }\n}\n",
        QUrl(),
    )
    assert component.status() == QQmlComponent.Ready, component.errorString()
    root = component.create()
    assert root is not None, component.errorString()
    view.setContent(QUrl(), component, root)
    view.show()
    pump(qapp)
    try:
        yield root
    finally:
        view.hide()
        view.setSource(QUrl())
        qapp.processEvents()
        if isValid(root):
            delete(root)
        if isValid(view):
            delete(view)


def _time_until(qapp: QApplication, done, limit: float = 3.0) -> float:  # noqa: ANN001
    """Milliseconds from now until `done()`, or the limit."""
    start = time.monotonic()
    while not done() and time.monotonic() - start < limit:
        qapp.processEvents()
    return (time.monotonic() - start) * 1000


def _flip(qapp: QApplication, probe: object, pace: float, reach: float) -> tuple[QQuickItem, QQuickItem]:
    """Set the level on the probe's Motion and flip its Switch on; returns the track and the thumb."""
    probe.setProperty("pace", pace)
    probe.setProperty("reach", reach)
    pump(qapp)
    switch = qml(probe, "sw")
    track = qml(probe, "shape")
    thumb = qml(probe, "switchThumb")
    switch.setProperty("checked", not switch.property("checked"))
    return track, thumb


@pytest.mark.parametrize("level", ["normal", "extra", "reduce", "off"])
def test_the_bridge_gives_each_level_its_pace_and_reach(
    qapp: QApplication, material_window: NativeWindow, level: str
) -> None:
    """Pace stretches durations, reach distances: Off 0 and 0, Reduce 1 and 0, Normal 1, 1, More 2.5, 4/3."""
    show_material(qapp, material_window)
    bridge = _publish(qapp, material_window, level)
    pace, reach = PACE_REACH[level]
    assert bridge.property("motionPace") == pytest.approx(pace)
    assert bridge.property("motionReach") == pytest.approx(reach)
    assert bridge.property("reduceMotion") is (level in ("reduce", "off"))


@pytest.mark.parametrize("level", ["normal", "extra", "reduce", "off"])
def test_the_page_fade_takes_the_levels_time(
    qapp: QApplication, material_window: NativeWindow, level: str
) -> None:
    """Reduce keeps the fade (it moves nothing); Off has none; More is 2.5 times as slow."""
    root = show_material(qapp, material_window)
    _publish(qapp, material_window, level)
    assert int(root.property("enterMs")) == LEVEL_TIMES[level][0]


@pytest.mark.parametrize(("speed", "ms"), [("Slower", 450), ("Normal", 300), ("Faster", 180), ("Off", 0)])
def test_motion_speed_scales_the_page_fade(
    qapp: QApplication, material_window: NativeWindow, speed: str, ms: int
) -> None:
    """Look > Advanced > Motion > Speed: Slower is 1.5 times the time, Faster 0.6, Off is the Off level."""
    root = show_material(qapp, material_window)
    _publish(qapp, material_window, "normal", speed)
    assert int(root.property("enterMs")) == ms


@pytest.mark.parametrize("level", ["normal", "extra", "reduce", "off"])
def test_a_switch_thumb_travels_for_the_levels_time(
    qapp: QApplication, switch_probe: object, level: str
) -> None:
    """Measured on a real Switch: how long its thumb takes to arrive after a flip."""
    pace, reach = PACE_REACH[level]
    _, thumb = _flip(qapp, switch_probe, pace, reach)
    travel = _time_until(qapp, lambda: abs(float(thumb.property("x")) - 24) < 0.5)
    expected = LEVEL_TIMES[level][1]
    if expected == 0:
        assert travel < 120, f"{level}: the thumb should jump, took {travel:.0f} ms"
    else:
        # The ease-out curve is within half a pixel of the end before its last tenth, so the band sits below.
        assert expected * 0.6 <= travel <= expected * 1.3, f"{level}: {travel:.0f} ms, wanted {expected}"


@pytest.mark.parametrize(("pace", "reach", "fades"), [(1.0, 0.0, True), (0.0, 0.0, False), (1.0, 1.0, True)])
def test_a_switch_track_fades_under_reduce_and_normal_but_not_off(
    qapp: QApplication, switch_probe: object, pace: float, reach: float, fades: bool
) -> None:
    """Reduce keeps the short fades (the track colour takes about 200 ms), Off has none."""
    track, _ = _flip(qapp, switch_probe, pace, reach)
    _time_until(qapp, lambda: False, 0.04)
    mid = QColor(track.property("color"))
    _time_until(qapp, lambda: False, 0.5)
    settled = QColor(track.property("color"))
    assert (mid != settled) is fades, f"pace {pace} reach {reach}: {mid.name()} then {settled.name()}"
