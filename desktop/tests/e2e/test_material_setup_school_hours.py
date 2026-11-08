# ruff: noqa: F811
"""Material 3 setup, Week step: the school start and end boxes show the clock in the 12 hour words, and
typing 24 hour words is read and shown the same way. Needs the real local server and a new account."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.tests.day.support_material_window import qapp  # noqa: E402, F401
from desktop.tests.test_material_account_setup import (  # noqa: E402
    Launches,
    account,
    create,
    look_file,
    through_recovery,
)
from desktop.tests.test_material_account_setup import named as account_named  # noqa: E402
from desktop.tests.test_material_account_setup import pump as account_pump  # noqa: E402


def test_setup_wizard_school_row_format(qapp: QApplication, tmp_path: Path) -> None:
    look_file().parent.mkdir(parents=True, exist_ok=True)
    look_file().write_text('{"surface": "material"}\n')
    made = Launches(qapp, tmp_path)
    try:
        win = made.launch()
        win.resize(1280, 800)
        account_pump(qapp, 10)
        bridge = account(win)
        create(qapp, win, "audit_student")
        through_recovery(qapp, win)
        bridge.setupNext()  # Style -> Week
        account_pump(qapp, 10)

        start_inputs = account_named(win, "setupSchoolStartInput")
        end_inputs = account_named(win, "setupSchoolEndInput")
        assert len(start_inputs) > 0, "setupSchoolStartInput must exist on setup Week page"
        assert len(end_inputs) > 0, "setupSchoolEndInput must exist on setup Week page"

        start_text = str(start_inputs[0].property("text"))
        assert start_text == "8:00 AM", f"Expected default start '8:00 AM', got {start_text!r}"

        end_input = end_inputs[0]
        end_input.forceActiveFocus()
        account_pump(qapp, 5)
        end_input.setProperty("text", "14:45")
        QTest.keyClick(win._material_page._quick, Qt.Key.Key_Return)
        account_pump(qapp, 10)

        end_text = str(end_input.property("text"))
        assert end_text == "2:45 PM", f"Expected 14:45 to format to '2:45 PM', got {end_text!r}"
    finally:
        made.close()
        look_file().unlink(missing_ok=True)
