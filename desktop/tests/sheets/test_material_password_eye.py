# ruff: noqa: F811
"""The password eye on a Material account field: clicking Show puts the password in view, clicking Hide
puts the dots back. A field that is not a password has no eye."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QUrl  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickView  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.tests.day.support_material_window import qapp  # noqa: E402, F401
from desktop.tests.material_support import pump  # noqa: E402

QML = Path(__file__).parents[2] / "native" / "material" / "qml"
TYPED = "my-long-test-password"


def _shown(field: QQuickItem) -> bool:
    """Whether the field draws the typed words; hidden, it draws one dot per letter instead."""
    return str(field.property("displayText")) == TYPED


def _click(view: QQuickView, item: QQuickItem) -> None:
    centre = item.mapToScene(item.boundingRect().center()).toPoint()
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=centre)
    pump(QApplication.instance(), 10)


def _field(qapp: QApplication, *, secret: bool) -> tuple[QQuickView, QQuickItem]:
    view = QQuickView()
    view.engine().addImportPath(str(QML))
    view.setSource(QUrl.fromLocalFile(str(QML / "account" / "AccountField.qml")))
    view.show()
    pump(qapp, 5)
    root = view.rootObject()
    assert root is not None
    root.setObjectName("loginPassword")
    root.setProperty("secret", secret)
    root.setProperty("text", TYPED)
    pump(qapp, 5)
    return view, root


def test_the_eye_shows_the_password_and_clicking_again_hides_it(qapp: QApplication) -> None:
    view, root = _field(qapp, secret=True)
    try:
        field = root.findChild(QQuickItem, "loginPasswordInput")
        eye = root.findChild(QQuickItem, "loginPasswordReveal")
        assert field is not None and eye is not None
        assert _shown(field) is False, "dots until the eye is clicked"
        assert eye.property("text") == "Show"
        assert eye.property("accessName") == "Show password"

        _click(view, eye)
        assert _shown(field) is True, "the password is in view"
        assert field.property("text") == TYPED
        assert eye.property("text") == "Hide"
        assert eye.property("accessName") == "Hide password"

        _click(view, eye)
        assert _shown(field) is False, "dots again"
        assert eye.property("text") == "Show"
    finally:
        view.close()
        del view
        pump(qapp)


def test_a_field_that_is_not_a_password_has_no_eye(qapp: QApplication) -> None:
    view, root = _field(qapp, secret=False)
    try:
        eye = root.findChild(QQuickItem, "loginPasswordReveal")
        field = root.findChild(QQuickItem, "loginPasswordInput")
        assert eye is not None and field is not None
        assert eye.isVisible() is False
        assert _shown(field) is True
    finally:
        view.close()
        del view
        pump(qapp)
