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


def _without_widgets_buttons(shell: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Make the Widgets buttons the More rows used to press unfindable, and say which names were asked."""
    asked: list[str] = []
    real = shell.findChild

    def find(kind, name="", *args, **kwargs):
        if name in HIDDEN:
            asked.append(name)
            return None
        return real(kind, name, *args, **kwargs)

    monkeypatch.setattr(shell, "findChild", find)
    return asked


HIDDEN = ("runningLate", "quickFocusAction", "replanAll", "helpButton", "aboutButton", "signOut")


def test_more_rows_work_without_any_widgets_button(
    shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = _without_widgets_buttons(shell, monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(shell, "_quick_focus", lambda: calls.append("quickFocusAction"))
    monkeypatch.setattr(shell, "_open_help", lambda: calls.append("helpButton"))
    monkeypatch.setattr(shell, "_open_about", lambda: calls.append("aboutButton"))
    monkeypatch.setattr(shell.session, "solve", lambda **kw: calls.append(f"solve {kw}"))
    monkeypatch.setattr(shell, "_log_out", lambda: calls.append("signOut asked"))

    sheets.openMore()
    rows = {row["id"]: row for row in sheets.moreEntries if row["id"]}
    labels = {name: rows[name]["label"] for name in HIDDEN}
    assert labels == {
        "runningLate": "Running late",
        "quickFocusAction": "Quick focus",
        "replanAll": "Replan all my homework",
        "helpButton": "Help",
        "aboutButton": "About FlexWeek",
        "signOut": "Sign out",
    }
    assert all(rows[name]["enabled"] for name in HIDDEN)

    sheets.moreAction("runningLate")
    assert sheets.kind == "late"
    sheets.forceClose()
    for name in ("quickFocusAction", "replanAll", "helpButton", "aboutButton", "signOut"):
        sheets.openMore()
        sheets.moreAction(name)
        assert sheets.moreOpen is False
    assert calls == [
        "quickFocusAction",
        "solve {'everything': True}",
        "helpButton",
        "aboutButton",
        "signOut asked",
    ]
    assert asked == []


def test_more_rows_grey_while_a_save_is_running(shell: NativeWindow, sheets, monkeypatch) -> None:
    _without_widgets_buttons(shell, monkeypatch)
    pressed: list[str] = []
    monkeypatch.setattr(shell, "_log_out", lambda: pressed.append("signOut"))
    monkeypatch.setattr(shell, "_open_help", lambda: pressed.append("helpButton"))
    shell.session.busy = True
    try:
        sheets.openMore()
        rows = {row["id"]: row for row in sheets.moreEntries if row["id"]}
        assert rows["runningLate"]["enabled"] is False
        assert rows["signOut"]["enabled"] is False
        assert rows["helpButton"]["enabled"] is True
        sheets.moreAction("signOut")
        assert pressed == []
        sheets.moreAction("helpButton")
        assert pressed == ["helpButton"]
    finally:
        shell.session.busy = False
