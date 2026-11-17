"""Material drawer: the count beside "No time yet" counts what the drawer lists, the cards and the lines
for homework that has minutes no session holds ("Science poster · 1 h with no time")."""

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


def test_the_count_includes_the_lines_for_homework_with_no_session(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    window.session.homework_remainders = lambda: [("Science poster", 60), ("History essay", 45)]
    _publish(window, qapp)

    assert "Science poster · 1 h with no time" in str(_qml(root, "homeworkDrawer").property("leftover"))
    assert _qml(root, "homeworkCount").property("text") == "3"


def test_the_count_is_zero_when_nothing_is_listed(qapp, window) -> None:
    root = _reset(window, qapp)
    window.session.homework_remainders = lambda: []
    _publish(window, qapp)

    assert _qml(root, "homeworkCount").property("text") == "0"
