"""Plan with homework left over asks "Before planning" on Material's own prompt, with the Widgets words and
answers, and no Widgets sheet opens over it."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import show_material
from desktop.tests.sheets.support_material_sheets import click, find
from desktop.tests.window_support import qapp  # noqa: F401

pytestmark = pytest.mark.real_surface

LEFT = [
    {"id": "late", "title": "Essay", "left_over_state": "overdue"},
    {"id": "carry", "title": "Math", "left_over_state": "carried"},
]


def _asked(qapp, window: NativeWindow, monkeypatch):
    root = show_material(qapp, window)
    monkeypatch.setattr(window, "_unfinished_items", lambda: LEFT)
    said: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(window.session, "plan_left", lambda ids: said.append(("plan", list(ids))))
    monkeypatch.setattr(window.session, "did_these", lambda ids: said.append(("did", list(ids))))
    window._material_page.bridge.plan()
    return root, said


def test_the_question_uses_the_widgets_words_and_answers(qapp, window, monkeypatch) -> None:
    root, said = _asked(qapp, window, monkeypatch)
    ask = window._material_page.bridge.sheets.ask
    assert ask["title"] == "Before planning"
    assert ask["body"] == "1 overdue, 1 left from last week"
    labels = [answer["label"] for answer in ask["answers"]]
    assert labels == ["Plan into this week", "Mark as finished", "Not now"]
    assert find(root, "sheetPrompt").property("visible")
    assert said == []


@pytest.mark.parametrize(
    ("button", "expected"),
    [("prompt_plan", [("plan", ["late", "carry"])]), ("prompt_did", [("did", ["late", "carry"])])],
)
def test_the_answers_do_what_the_widgets_sheet_did(qapp, window, monkeypatch, button, expected) -> None:
    root, said = _asked(qapp, window, monkeypatch)
    click(window, find(root, button))
    assert said == expected
    assert not window._material_page.bridge.sheets.ask


@pytest.mark.parametrize("how", ["not", "esc"])
def test_not_now_and_escape_do_not_ask_again_this_week(qapp, window, monkeypatch, how) -> None:
    root, said = _asked(qapp, window, monkeypatch)
    window.session.plan_asked_week = None
    if how == "not":
        click(window, find(root, "prompt_not"))
    else:
        window._material_page.bridge.sheets.closeSheet()
    assert said == []
    assert window.session.plan_asked_week == window.session.week_start
