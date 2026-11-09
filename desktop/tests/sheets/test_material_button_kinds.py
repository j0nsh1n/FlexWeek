# ruff: noqa: F811
"""Which kind each Material button is. The rule is one filled button per screen (the student's answer),
so nothing is left outlined, each screen and each settings prompt has at most one filled button, and the
Widgets styles control on the Look page is a plain text button.

These read the QML source and the prompts' button lists, not pixels, so every screen and every prompt is
covered however it is reached. What a filled button looks like is judged on the pictures.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from desktop.tests.sheets.support_material_sheet_fixtures import QML, qapp  # noqa: E402,F401

ROOT = Path(__file__).resolve().parents[3]
LOOK = QML / "settings" / "LookSection.qml"
_FILLED = re.compile(r'kind:\s*"filled"')
_OUTLINED = re.compile(r'kind\s*:\s*["\']outlined["\']')
_BUTTON_FILLED = re.compile(r"Button\s*\{[^{}]*kind:\s*\"filled\"", re.DOTALL)


def test_no_outlined_buttons_are_left() -> None:
    """No QML control sets kind to outlined; leftover uses became text."""
    found: list[str] = []
    for path in QML.rglob("*.qml"):
        if _OUTLINED.search(path.read_text(encoding="utf-8")):
            found.append(str(path.relative_to(ROOT)))
    assert found == []


def test_each_screen_has_at_most_one_filled_button() -> None:
    """Main Week has only Plan; Add homework one; Day only NowCard Start focus; Advanced one."""
    week_text = (QML / "views" / "WeekView.qml").read_text(encoding="utf-8")
    assert _FILLED.findall(week_text) == []

    drawer_text = (QML / "week" / "HomeworkDrawer.qml").read_text(encoding="utf-8")
    # Plan is filled while something waits and a text button when nothing does.
    assert len(re.findall(r'kind:[^\n]*"filled"', drawer_text)) == 1
    assert 'objectName: "planHomework"' in drawer_text

    hw_sheet_text = (QML / "sheets" / "HomeworkSheet.qml").read_text(encoding="utf-8")
    assert len(_BUTTON_FILLED.findall(hw_sheet_text)) == 1
    assert 'objectName: "homeworkNext"' in hw_sheet_text

    now_card_text = (QML / "day" / "NowCard.qml").read_text(encoding="utf-8")
    assert len(_BUTTON_FILLED.findall(now_card_text)) == 1
    assert 'text: root.focusTitle ? "Start " + root.focusTitle : "Start focus"' in now_card_text

    day_lists_text = (QML / "day" / "DayLists.qml").read_text(encoding="utf-8")
    assert _BUTTON_FILLED.findall(day_lists_text) == []

    adv_text = (QML / "settings" / "AdvancedPage.qml").read_text(encoding="utf-8")
    assert len(_BUTTON_FILLED.findall(adv_text)) == 1
    assert 'objectName: "advancedDone"' in adv_text
    assert re.search(r'objectName: "fixAll"[\s\S]*?kind: "tonal"', adv_text)

    focus_text = (QML / "focus" / "FocusScreen.qml").read_text(encoding="utf-8")
    # Start and Pause are both filled in source; only one is visible at a time.
    assert len(_BUTTON_FILLED.findall(focus_text)) == 2
    assert 'objectName: "focusStart"' in focus_text
    assert 'objectName: "focusPause"' in focus_text
    assert re.search(r'objectName: "focusSkip"[\s\S]*?kind: "text"', focus_text)
    assert re.search(r'objectName: "focusFinished"[\s\S]*?kind: "tonal"', focus_text)


def test_widgets_styles_is_a_text_button_and_look_has_at_most_one_filled() -> None:
    """Look's Widgets styles control is kind text; the Look page keeps at most one filled button."""
    look_text = LOOK.read_text(encoding="utf-8")
    use = re.search(
        r'objectName:\s*"useWidgets"[\s\S]*?kind:\s*"([^"]+)"',
        look_text,
    )
    assert use is not None
    assert use.group(1) == "text"
    filled = re.findall(r'kind:\s*"filled"', look_text)
    assert len(filled) <= 1


def _prompt_button_lists() -> list[tuple[str, list[dict]]]:
    """Every `buttons: [...]` a settings Prompt is given, evaluated as the JavaScript it is."""
    from PySide6.QtQml import QJSEngine

    engine = QJSEngine()
    found: list[tuple[str, list[dict]]] = []
    for path in sorted(QML.rglob("*.qml")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"\bbuttons:\s*\[", text):
            depth, end = 0, match.end() - 1
            for end in range(match.end() - 1, len(text)):
                depth += {"[": 1, "]": -1}.get(text[end], 0)
                if depth == 0:
                    break
            value = engine.evaluate("(" + text[match.end() - 1 : end + 1] + ")")
            assert not value.isError(), f"{path.name}: {value.toString()}"
            found.append((path.name, value.toVariant()))
    return found


def test_every_settings_prompt_has_at_most_one_filled_button(qapp: QGuiApplication) -> None:
    """Each prompt is its own screen: one filled button at most."""
    lists = _prompt_button_lists()
    names = {name for name, _buttons in lists}
    assert {"AdvancedPage.qml", "SettingsView.qml"} <= names, names
    for name, buttons in lists:
        filled = [button["label"] for button in buttons if button.get("kind", "text") == "filled"]
        assert len(filled) <= 1, f"{name}: {filled}"
