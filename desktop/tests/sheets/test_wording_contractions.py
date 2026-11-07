"""Labels have no full stop, sentences have one, and the app's own words use contractions.

Expected copy is from 03-wording-audit.md T-W25 and decisions.md 2026-10-13, not from reading the
code's current output. The scan walks desktop/native string literals a student can be shown.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.settings import HELP_PLANNING, HELP_SCREENS
from desktop.native.widgets import PlanReview
from desktop.native.window import PLAN_TIP
from desktop.tests.window_support import qapp  # noqa: F401

NATIVE = Path(__file__).resolve().parents[2] / "native"
POLISH_A = frozenset(
    {
        "look_editor.py",
        "look.py",
        "previews.py",
        "look_preview.py",
        "calendar.py",
        "hours/canvas.py",
    }
)
UNCONTRACTED = re.compile(
    r"\b(is not|does not|do not|it is|cannot|you are|that is|there is)\b",
    re.IGNORECASE,
)
# Phrases that must stay: a greeting, two "how late you are" prompts, an import with no changes, and
# a block the editor cannot rewrite in place (the "as it is" is the thing being kept).
ALLOWED = frozenset(
    {
        "Ready when you are",
        "Say how late you are and preview what moves. Nothing changes until you accept it.",
        "Behind today? Say how late you are, and FlexWeek moves the rest of today's homework later.",
        "Nothing in it is different from your account.",
        "FlexWeek can't keep this block as it is. Check its title, days and times.",
    }
)
LOG_FUNCS = frozenset({"debug", "info", "warning", "error", "exception", "critical", "log"})
WEEK = "2026-10-12"


def _call_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _skip_ids(tree: ast.AST) -> set[int]:
    skip: set[int] = set()

    def first_doc(body: list[ast.stmt]) -> None:
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            skip.add(id(body[0].value))

    first_doc(tree.body)  # type: ignore[attr-defined]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first_doc(node.body)
        if isinstance(node, (ast.Raise, ast.Assert)):
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    skip.add(id(child))
                if isinstance(child, ast.JoinedStr):
                    skip.add(id(child))
        if isinstance(node, ast.Call) and _call_name(node.func) in LOG_FUNCS:
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    skip.add(id(child))
                if isinstance(child, ast.JoinedStr):
                    skip.add(id(child))
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant):
                    skip.add(id(value))
    return skip


def _joined(node: ast.JoinedStr) -> str:
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        else:
            parts.append("{}")
    return "".join(parts)


def user_facing_strings(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _skip_ids(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.JoinedStr):
            text = _joined(node)
            if text:
                found.append((node.lineno, text))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value:
            found.append((node.lineno, node.value))
    return found


def test_user_facing_copy_uses_contractions() -> None:
    leftover: list[str] = []
    for path in sorted(NATIVE.rglob("*.py")):
        rel = path.relative_to(NATIVE).as_posix()
        if rel in POLISH_A:
            continue
        for lineno, text in user_facing_strings(path):
            if not UNCONTRACTED.search(text):
                continue
            if text in ALLOWED:
                continue
            leftover.append(f"{rel}:{lineno}: {text}")
    assert leftover == []


def test_the_controllers_notices_use_contractions() -> None:
    source = (NATIVE / "controller.py").read_text(encoding="utf-8")
    for wanted in (
        "There's nothing to copy from last week yet.",
        "That's outside the hours FlexWeek plans in, so it stayed where it was.",
        "That block isn't on that date.",
        "That change can't be undone. Reload and try again.",
        "That change can't be redone. Reload and try again.",
        "Undo did not go through. Your week was reloaded as it's saved.",
        "Uncheck what can't be added before saving.",
        "There's nothing available to add.",
        " remains, but it doesn't fit the 15-minute planning grid.",
        " can't fit the 15-minute grid and has not been ",
        "Place a work block that isn't finished before starting focus.",
    ):
        assert wanted in source, wanted


def test_help_for_planning_and_the_day_screen_use_contractions() -> None:
    assert HELP_PLANNING == (
        "Add homework with its due date and length. Press Plan my homework and FlexWeek finds free time for "
        "it in your study hours, around your fixed times, before it's due. Homework that already has a time "
        "keeps it. Replan all starts fresh but keeps pinned homework. Anything that doesn't "
        "fit stays under Not placed yet, and Details says why. From the keyboard, press Ctrl+K and type Plan."
    )
    assert HELP_SCREENS[0] == (
        "Day",
        "One day hour by hour, with homework that isn't placed yet beside it, ready to drag in.",
    )


def test_the_plan_button_s_tip_uses_a_contraction() -> None:
    assert PLAN_TIP == (
        "Find a time for homework that has none, around your fixed times and before it's due. Homework "
        "that already has a time keeps it."
    )


def test_a_fair_share_row_is_a_sentence(qapp: QApplication) -> None:  # noqa: F811
    trace = {
        "placed": [],
        "unplaced": [],
        "moves": [],
        "explanations": [],
        "shares": [
            {
                "title": "Science project",
                "this_week_min": 60,
                "left_min": 60,
                "due": "2026-10-13",
            }
        ],
    }
    assert PlanReview().rows_for(trace, {}, WEEK) == [
        "Science project (due Tue 13 Oct): 1 h planned this week. FlexWeek saves the other 1 h "
        "for next week so this week isn't overloaded. Press Plan next week to place it."
    ]


def test_thats_in_the_past_is_not_used_anywhere_in_native() -> None:
    hits = [
        path for path in NATIVE.rglob("*.py") if "That's in the past." in path.read_text(encoding="utf-8")
    ]
    assert hits == []
