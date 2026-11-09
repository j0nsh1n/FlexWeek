# ruff: noqa: F811
"""The Material 3 account field: Return commits what was typed, rebinds the text, and submits the form."""

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


def test_account_field_commits_and_rebinds_on_return(qapp: QApplication) -> None:
    view = QQuickView()
    try:
        view.engine().addImportPath(str(QML))
        view.setSource(QUrl.fromLocalFile(str(QML / "account" / "AccountField.qml")))
        view.show()
        pump(qapp, 5)

        root = view.rootObject()
        assert root is not None

        committed_values: list[str] = []
        submitted_count: list[bool] = []
        login_submitted_payload: list[str] = []

        root.setProperty("text", "initial_user")
        root.committed.connect(lambda val: committed_values.append(str(val)))
        root.committed.connect(lambda val: root.setProperty("text", val))
        root.submitted.connect(lambda: submitted_count.append(True))
        root.submitted.connect(lambda: login_submitted_payload.append(str(root.property("text"))))

        root.setObjectName("loginUsername")
        input_item = root.findChild(QQuickItem, "loginUsernameInput")
        assert input_item is not None

        input_item.setProperty("text", "audit_student_2026")
        input_item.forceActiveFocus()
        pump(qapp, 2)

        QTest.keyClick(view, Qt.Key.Key_Return)
        pump(qapp, 5)

        assert "audit_student_2026" in committed_values, (
            f"Expected 'audit_student_2026' in committed: {committed_values}"
        )
        assert len(submitted_count) >= 1, f"Expected submitted signal, got {len(submitted_count)}"
        assert "audit_student_2026" in login_submitted_payload, (
            f"Expected 'audit_student_2026' in login submission: {login_submitted_payload}"
        )
        assert input_item.property("text") == "audit_student_2026"
    finally:
        view.close()
        del view
        pump(qapp)
