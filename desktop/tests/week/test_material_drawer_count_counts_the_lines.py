"""Material drawer: the count beside "No time yet" counts each homework the drawer lists once, as a card
or as a line for minutes no session holds ("Science poster · 1 h with no time"), or both."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import timedelta

from desktop.tests.week.support_material import (
    _homework,
    _pump,
    _qml,
    _reset,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401


def _publish(window, qapp) -> None:
    window._material_page.publish()
    _pump(qapp)


def test_the_count_includes_each_homework_with_a_line_and_no_card(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    window.session.homework_remainders = lambda: [
        ("Science poster", 60, "poster"),
        ("History essay", 45, "essay"),
    ]
    _publish(window, qapp)

    assert "Science poster · 1 h with no time" in str(_qml(root, "homeworkDrawer").property("leftover"))
    assert _qml(root, "homeworkCount").property("text") == "3"


def test_the_count_is_zero_when_nothing_is_listed(qapp, window) -> None:
    root = _reset(window, qapp)
    window.session.homework_remainders = lambda: []
    _publish(window, qapp)

    assert _qml(root, "homeworkCount").property("text") == "0"


def test_a_homework_with_a_card_and_a_line_counts_once(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    window.session.homework_remainders = lambda: [
        ("Math worksheet", 10, "sheet"),
        ("History essay", 45, "essay"),
    ]
    _publish(window, qapp)

    assert _qml(root, "homeworkCount").property("text") == "2"


def test_two_homework_with_the_same_title_count_as_two(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=4)).isoformat()
    later = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "spell1", "Spelling practice", 30, due)
    _homework(window, "spell2", "Spelling practice", 30, later)
    settled(qapp, window)
    window.session.homework_remainders = lambda: []
    _publish(window, qapp)

    assert _qml(root, "homeworkCount").property("text") == "2"


def test_a_title_with_a_dot_in_it_still_counts_once(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "bio", "Bio · chapter 4", 30, due)
    settled(qapp, window)
    window.session.homework_remainders = lambda: [("Bio · chapter 4", 10, "bio")]
    _publish(window, qapp)

    assert _qml(root, "homeworkCount").property("text") == "1"
