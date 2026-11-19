"""Fixes from the code review of the Material notice and prompt work: the timer's replace question is
Material's own, the destructive choice card is the red one, and a long notice fits inside the window."""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtQml import QQmlProperty
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import named, pump, visuals
from desktop.tests.sheets.support_prompt_walk import bridge_sheets as sheets_of
from desktop.tests.sheets.support_prompt_walk import prompt_item, week_with_school
from desktop.tests.window_support import qapp  # noqa: F401


def _button(prompt, name: str):
    found = [item for item in visuals(prompt) if str(item.objectName()) == name]
    assert found, name
    return found[0]


def _card(prompt, card_id: str):
    return _button(prompt, f"prompt_card_{card_id}")


def test_replacing_a_running_timer_asks_on_a_material_prompt(qapp, window: NativeWindow, monkeypatch) -> None:
    """Start focus while a timer runs: the question is Material's, keep first."""
    week_with_school(qapp, window)
    replaced: list[bool] = []
    monkeypatch.setattr(window.session, "confirm_replace_focus", lambda: replaced.append(True) or False)
    window.session.focus_replace_needed.emit("History essay", "Math worksheet")
    pump(qapp, 30)
    ask = sheets_of(window).ask
    assert ask["id"] == "replace-focus"
    assert ask["title"] == "Replace timer"
    assert ask["body"] == "Stop the timer for History essay and start Math worksheet instead?"
    assert [(a["label"], a["kind"]) for a in ask["answers"]] == [
        ("Keep current timer", "text"),
        ("Replace timer", "danger"),
    ]
    sheets_of(window).answer("keep")
    pump(qapp, 10)
    assert replaced == [], "Keep current timer replaced it"
    window.session.focus_replace_needed.emit("History essay", "Math worksheet")
    pump(qapp, 30)
    sheets_of(window).answer("replace")
    pump(qapp, 10)
    assert replaced == [True]


def test_this_week_and_later_is_the_red_card_and_delete_is_red_only_while_it_is_picked(
    qapp, window: NativeWindow
) -> None:
    week_with_school(qapp, window)
    sheets = sheets_of(window)
    sheets.askDeleteBlock("school", 1)
    pump(qapp, 30)
    prompt = prompt_item(window)
    def confirm_kind() -> str:
        # The footer is rebuilt when the pick changes, so the button is looked up each time.
        return str(_button(prompt, "prompt_confirm").property("kind"))

    assert confirm_kind() == "filled", "a card you can undo is picked, so Delete is not red"
    every = _card(prompt, "every")
    error = every.property("accent")
    primary = _card(prompt, "day").property("accent")
    assert error != primary, "the destructive card has its own accent"
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Down)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Down)
    pump(qapp, 20)
    assert every.property("picked") is True
    assert confirm_kind() == "danger"
    assert QQmlProperty.read(every, "border.color") == error
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Up)
    pump(qapp, 20)
    assert confirm_kind() == "filled"


def test_a_notice_of_several_lines_stays_inside_the_window_and_shows_every_line(
    qapp, window: NativeWindow
) -> None:
    week_with_school(qapp, window)
    page = window._material_page
    lines = [
        "Guitar practice now covers History essay. Find a new time for it.",
        "Guitar practice now covers Math worksheet. Find a new time for it.",
        "Guitar practice now covers Biology reading. Find a new time for it.",
        "And 2 more.",
    ]
    page.bridge.note("\n".join(lines), action="UNDO")
    pump(qapp, 30)
    (bar,) = [item for item in named(page.root, "materialSnackbar") if item.property("visible")]
    shell = page.root
    left = bar.mapToScene(QPointF(0, 0)).x()
    assert left >= 0 and left + float(bar.property("width")) <= float(shell.property("width"))
    assert float(bar.property("width")) <= float(shell.property("width")) - 48 + 0.5
    text = [item for item in visuals(bar) if str(item.property("text") or "") == "\n".join(lines)]
    assert text, "the notice's words are not on the bar"
    assert float(text[0].property("height")) + 20 <= float(bar.property("height")), "a line is cut off"
    assert float(bar.property("height")) > 48
    assert float(text[0].property("paintedWidth")) <= float(text[0].property("width")) + 1, "words run off"

    long_line = " ".join(lines[:3])
    page.bridge.note(long_line, action="UNDO")
    pump(qapp, 30)
    words = [item for item in visuals(bar) if str(item.property("text") or "") == long_line]
    assert words, "the long notice's words are not on the bar"
    assert float(bar.property("width")) <= float(shell.property("width")) - 48 + 0.5
    assert float(words[0].property("paintedWidth")) <= float(words[0].property("width")) + 1, "words run off"
    assert float(words[0].property("height")) + 20 <= float(bar.property("height")), "a line is cut off"


def test_after_the_notices_undo_on_day_the_keyboard_is_on_the_day(qapp, window: NativeWindow) -> None:
    week_with_school(qapp, window)
    page = window._material_page
    page.bridge.open_page("day")
    pump(qapp, 30)
    page.bridge.note("Moved School to Thu 8:00 AM.", action="UNDO")
    pump(qapp, 20)
    (bar,) = [item for item in named(page.root, "materialSnackbar") if item.property("visible")]
    bar.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(page._quick, Qt.Key.Key_Return)
    pump(QApplication.instance(), 60)
    item = page._quick.quickWindow().activeFocusItem()
    names = []
    while item is not None:
        names.append(str(item.objectName()))
        item = item.parentItem()
    assert "weekBlock" in names or "dayScroller" in names, " < ".join(names) or "nothing"


def _focus_chain(window: NativeWindow) -> list[str]:
    item = window._material_page._quick.quickWindow().activeFocusItem()
    names = []
    while item is not None:
        names.append(str(item.objectName()) + ":" + str(item.property("title") or ""))
        item = item.parentItem()
    return names


def test_the_notices_undo_gives_the_keyboard_back_to_the_block_it_left(qapp, window: NativeWindow) -> None:
    """On the Week: keyboard on School, Tab to the notice, Enter on Undo: the keyboard is on School again."""
    week_with_school(qapp, window)
    page = window._material_page
    (school,) = [b for b in named(page.root, "weekBlock") if b.property("title") == "School"][:1]
    school.forceActiveFocus()
    pump(qapp)
    page.bridge.note("Moved School to Thu 8:00 AM.", action="UNDO")
    pump(qapp, 20)
    (bar,) = [item for item in named(page.root, "materialSnackbar") if item.property("visible")]
    bar.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(page._quick, Qt.Key.Key_Return)
    pump(QApplication.instance(), 60)
    assert "weekBlock:School" in _focus_chain(window), " < ".join(_focus_chain(window))


def test_a_reminder_strip_sits_above_a_notice_of_several_lines(qapp, window: NativeWindow) -> None:
    """Got it stays clickable: the strip moves up with a notice that grew to several lines."""
    week_with_school(qapp, window)
    page = window._material_page
    window.alert_strip.add([{"title": "Guitar practice starts soon", "body": "7:15 PM · Thu"}])
    line = "Guitar practice now covers History essay. Find a new time for it."
    page.bridge.note("\n".join([line] * 3), action="UNDO")
    pump(qapp, 30)
    (bar,) = [item for item in named(page.root, "materialSnackbar") if item.property("visible")]
    (strip,) = [item for item in named(page.root, "materialAlertStrip") if item.property("visible")]
    bar_top = bar.mapToScene(QPointF(0, 0)).y()
    strip_bottom = strip.mapToScene(QPointF(0, float(strip.property("height")))).y()
    assert float(bar.property("height")) > 48, "the notice did not grow, so the test says nothing"
    assert strip_bottom <= bar_top - 8, (strip_bottom, bar_top)


def test_the_notices_undo_text_reads_at_4_5_to_1_in_every_look() -> None:
    import json
    from pathlib import Path as _Path

    from desktop.native.material import theme

    tokens = json.loads((_Path(theme.__file__).parent / "tokens.json").read_text())

    def lum(colour: str) -> float:
        h = colour.lstrip("#")[-6:]
        rgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    low = []
    for name, scheme in tokens.items():
        if "inversePrimary" not in scheme:
            continue
        a, b = sorted((lum(scheme["inversePrimary"]), lum(scheme["inverseSurface"])), reverse=True)
        if (a + 0.05) / (b + 0.05) < 4.5:
            low.append((name, round((a + 0.05) / (b + 0.05), 2)))
    assert low == []
