# ruff: noqa: F811
"""The Material More menu: its rows, which are on, and what each one opens or presses.

Expected words and values come from the Widgets More menu and from the week the fixtures build (School
Monday to Friday, a History essay planned Thursday 18:45, so nothing is left over).
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QPushButton  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    open_light,
    qapp,
    sheets,
    shell,
)


def test_more_rows_and_what_each_opens(shell: NativeWindow, sheets) -> None:
    shell._material_page.bridge.openMore()
    rows = {row["id"]: row for row in sheets.moreEntries if row["id"]}
    headings = [row["heading"] for row in sheets.moreEntries if row["heading"]]
    assert headings == ["Planning", "Help and info", "Account"]
    assert rows["runningLate"]["enabled"] is True
    # The essay has its time, so nothing is left over.
    assert rows["unfinishedOpen"]["enabled"] is False
    assert rows["unfinishedOpen"]["detail"] == "None left"
    for name in ("weekListRow", "routinesButton", "quickFocusAction", "replanAll", "helpButton", "signOut"):
        assert name in rows

    sheets.moreAction("runningLate")
    assert sheets.kind == "late"
    assert sheets.moreOpen is False
    sheets.forceClose()

    sheets.openMore()
    sheets.moreAction("weekListRow")
    assert sheets.kind == "weekList"
    items = [row for row in sheets.form["rows"] if row["type"] == "item"]
    school = [row for row in items if row["title"] == "School"]
    assert len(school) == 5
    assert school[0]["detail"].endswith("Fixed time")
    assert any(row["title"] == "History essay" for row in items)
    assert [row["text"] for row in sheets.form["rows"] if row["type"] == "heading"][0].startswith("Monday")
    block = next(item for item in shell.session.blocks if item.get("assignment_id") == "essay")
    sheets.openFromList(block["id"], 3)
    assert sheets.kind == "homework"
    assert sheets.form["title"] == "History essay"
    sheets.forceClose()

    sheets.openMore()
    sheets.moreAction("routinesButton")
    assert sheets.kind == "routines"
    assert sheets.form["empty"] == "No routines saved yet."
    sheets.forceClose()

    sheets.openMore()
    sheets.moreAction("unfinishedOpen")
    assert sheets.kind == ""
    sheets.closeMore()


def test_more_actions_press_the_widgets_buttons_they_name(
    shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    pressed: list[str] = []
    fakes: dict[str, QPushButton] = {}

    def fake(name: str) -> QPushButton:
        if name not in fakes:
            button = QPushButton(name, shell)
            button.hide()
            button.clicked.connect(lambda _=False, which=name: pressed.append(which))
            fakes[name] = button
        return fakes[name]

    monkeypatch.setattr(sheets, "_button", fake)
    for name in ("quickFocusAction", "replanAll", "helpButton", "aboutButton", "signOut"):
        sheets.openMore()
        sheets.moreAction(name)
        assert sheets.moreOpen is False
    assert pressed == ["quickFocusAction", "replanAll", "helpButton", "aboutButton", "signOut"]
    fakes["helpButton"].setEnabled(False)
    sheets.openMore()
    sheets.moreAction("helpButton")
    assert pressed.count("helpButton") == 1
    sheets.closeMore()
