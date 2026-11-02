"""A play must not see or click a QML item that clipping has hidden.

The rectangles below are placed by these numbers, not by reading them back from a run.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtQuickWidgets import QQuickWidget  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from scripts.rig.play import qml_click_targets, qml_tree_entries  # noqa: E402

SHELL = """
import QtQuick
Item {
    objectName: "clipRoot"
    width: 200
    height: 100
    Item {
        objectName: "clipper"
        x: 0
        y: 0
        width: 80
        height: 40
        clip: true
        Rectangle {
            objectName: "inside"
            x: 10
            y: 10
            width: 20
            height: 20
        }
        Rectangle {
            objectName: "outside"
            x: 100
            y: 10
            width: 30
            height: 20
        }
        Rectangle {
            objectName: "partial"
            x: 70
            y: 10
            width: 30
            height: 20
        }
    }
    Rectangle {
        objectName: "hostEdge"
        x: -20
        y: 50
        width: 30
        height: 20
    }
}
"""


@pytest.fixture
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-qml-clip"])
    yield application


def _host(qapp: QApplication, tmp_path: Path) -> QQuickWidget:
    page = tmp_path / "clip.qml"
    page.write_text(SHELL, encoding="utf-8")
    widget = QQuickWidget()
    widget.resize(200, 100)
    widget.setSource(QUrl.fromLocalFile(str(page)))
    widget.show()
    qapp.processEvents()
    assert widget.rootObject() is not None
    assert widget.status() != QQuickWidget.Status.Error
    return widget


def _named(widget: QQuickWidget, name: str) -> list:
    return qml_click_targets([widget], "name", name)


def test_a_fully_clipped_item_is_neither_seen_nor_clicked(qapp: QApplication, tmp_path: Path) -> None:
    widget = _host(qapp, tmp_path)
    assert _named(widget, "inside")
    assert _named(widget, "outside") == []
    names = [row["objectName"] for row in qml_tree_entries(widget, widget, 0)]
    assert "outside" not in names
    assert "inside" in names


def test_a_click_lands_in_the_visible_part(qapp: QApplication, tmp_path: Path) -> None:
    widget = _host(qapp, tmp_path)
    partial = _named(widget, "partial")
    assert partial
    local = widget.mapFromGlobal(partial[0][1])
    assert 70 <= local.x() < 80
    edge = _named(widget, "hostEdge")
    assert edge
    landed = widget.mapFromGlobal(edge[0][1])
    assert 0 <= landed.x() < 10
