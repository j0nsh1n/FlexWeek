"""A Material status chip says its state in an icon and a word, not in colour alone, and Plan on the homework
drawer is a plain text button with its hint when nothing is left to plan.

How the chips and the button are coloured (the tint, the ink, the muted words) is judged on the pictures
(screens `week.material_homework_drawer` and `week.material_homework_drawer_all_planned`).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402

from desktop.native.material.theme import scheme, theme_object  # noqa: E402

QML = Path(__file__).resolve().parents[2] / "native" / "material" / "qml"
# QML engine/component/item form a cycle; keep them so the collector fixture does not see them.
_HOLD: list[object] = []


@pytest.fixture(scope="module")
def qapp() -> Iterator[QGuiApplication]:
    yield QGuiApplication.instance() or QGuiApplication(["flexweek-status-chips"])


def _theme() -> dict:
    return theme_object(scheme("Slate", "light", "std"), "comfortable", False, False)


def _component(source: bytes | None = None, url: Path | None = None) -> tuple[QQmlEngine, QQmlComponent]:
    engine = QQmlEngine()
    engine.addImportPath(str(QML))
    if url is not None:
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(url)))
    else:
        component = QQmlComponent(engine)
        component.setData(source or b"", engine.baseUrl())
    assert component.isReady(), component.errorString()
    _HOLD.extend((engine, component))
    return engine, component


def _item(component: QQmlComponent) -> QQuickItem:
    item = component.create()
    assert item is not None, component.errorString()
    _HOLD.append(item)
    return item


def test_status_chips_have_an_icon_and_a_word(qapp: QGuiApplication) -> None:
    _engine, component = _component(b"import components 1.0\nTag { width: 100; height: 20 }\n")
    for kind, icon_name in (("plenty", "check"), ("tight", "schedule"), ("cutting", "warning")):
        tag = _item(component)
        tag.setProperty("theme", _theme())
        tag.setProperty("kind", kind)
        tag.setProperty("text", f"Status {kind}")
        qapp.processEvents()

        icon = tag.findChild(QQuickItem, "icon")
        label = tag.findChild(QQuickItem, "label")
        assert icon is not None and label is not None
        assert icon.property("visible") is True
        assert icon.property("name") == icon_name
        assert label.property("text") == f"Status {kind}"

    plain = _item(component)
    plain.setProperty("theme", _theme())
    plain.setProperty("kind", "plain")
    plain.setProperty("text", "Plain text")
    qapp.processEvents()
    plain_icon = plain.findChild(QQuickItem, "icon")
    assert plain_icon.property("visible") is False or plain_icon.property("name") == ""


def test_plan_is_a_text_button_with_its_hint_when_nothing_is_left_to_plan(qapp: QGuiApplication) -> None:
    _engine, component = _component(url=QML / "week" / "HomeworkDrawer.qml")
    drawer = _item(component)
    drawer.setProperty("theme", _theme())
    drawer.setProperty("count", 0)
    qapp.processEvents()

    plan = drawer.findChild(QQuickItem, "planHomework")
    assert plan is not None
    assert plan.property("enabled") is False
    assert plan.property("kind") == "text"

    empty_box = drawer.findChild(QQuickItem, "homeworkEmpty")
    empty_text = drawer.findChild(QQuickItem, "homeworkEmptyText")
    assert empty_box is not None and empty_text is not None
    assert empty_box.property("visible") is True
    assert empty_text.property("text") == "Everything has a time."
