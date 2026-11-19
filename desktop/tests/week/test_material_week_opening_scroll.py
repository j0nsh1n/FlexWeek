"""Where the Material Week opens and where it stays: on the first block with now in view when both fit,
with now low in the view when they do not, an empty next week at 08:00, and the student's scroll kept
through a page change. Today brings now back.

Thursday 19:00 is the clock, School runs 08:00 to 14:30 on weekdays and the History essay is planned for
18:45. The expected places come from what the student should see (the first block near the top, now in
view), not from the scroll value the QML computes."""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPointF  # noqa: E402

from desktop.tests.week.support_material import (  # noqa: E402
    _block_named,
    _bridge,
    _named,
    _pump,
    _qml,
    _reset,
    _text_size,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: E402,F401

ROW_PX = 56


def _opened(window, qapp) -> QObject:
    """Material built fresh on a week that already holds its blocks, as a sign-in opens it: the window
    starts on Material before the seed adds anything, and the hours open only once."""
    window._drop_partial_material()
    return _reset(window, qapp)


def _scroller(root: QObject) -> QObject:
    return _qml(root, "weekScroller")


def _top(item: QObject, scroller: QObject) -> float:
    """How far below the scroll area's top the item's top edge is drawn, in pixels."""
    return item.mapToScene(QPointF(0, 0)).y() - scroller.mapToScene(QPointF(0, 0)).y()


def _in_view(item: QObject, scroller: QObject) -> bool:
    return _top(item, scroller) >= 0 and _top(item, scroller) + item.height() <= scroller.height() + 1


def _away(qapp, scroller: QObject) -> None:
    scroller.setProperty("contentY", 0.0)
    _pump(qapp, 20)


def _turn(qapp, window, name: str) -> None:
    getattr(_bridge(window).week, name)()
    settled(qapp, window)
    _pump(qapp, 60)


def test_this_week_opens_on_its_first_block_with_now_and_the_essay_in_view(qapp, window) -> None:
    root = _opened(window, qapp)
    _pump(qapp, 60)
    scroller = _scroller(root)
    school = _named(root, "weekBlock")[0]
    assert 0 <= _top(school, scroller) <= ROW_PX, "the week did not open on its first block (08:00)"
    assert _in_view(_named(root, "nowLine")[0], scroller), "now is out of view"
    assert _in_view(_block_named(root, "History essay"), scroller), "the planned essay is out of view"


def test_when_the_first_block_and_now_do_not_fit_together_now_is_low_in_the_view(qapp, window) -> None:
    school = next(block for block in window.session.blocks if block["id"] == "school")
    window.session.add_block({**school, "start": "01:00"})
    window.session.save()
    settled(qapp, window)
    root = _opened(window, qapp)
    _pump(qapp, 60)
    scroller = _scroller(root)
    line = _named(root, "nowLine")[0]
    assert _in_view(line, scroller), "now is out of view"
    share = _top(line, scroller) / scroller.height()
    assert 0.4 <= share <= 0.8, f"now sits at {share:.0%} of the view; it should be low in it, not at an edge"


def test_an_empty_next_week_opens_at_eight(qapp, window) -> None:
    root = _opened(window, qapp)
    _pump(qapp, 60)
    _turn(qapp, window, "next")
    scroller = _scroller(root)
    shown = [label for label in _named(root, "hourLabel") if 0 <= _top(label, scroller) < scroller.height()]
    first = str(min(shown, key=lambda label: _top(label, scroller)).property("text"))
    assert first.lstrip("0").startswith("8:00"), f"the hours open at {first}, not 08:00"


def test_a_page_change_leaves_the_week_where_the_student_scrolled_it(qapp, window) -> None:
    root = _opened(window, qapp)
    scroller = _scroller(root)
    _away(qapp, scroller)
    _bridge(window).showPage("month")
    _pump(qapp, 40)
    _bridge(window).showPage("week")
    _pump(qapp, 60)
    assert float(_scroller(root).property("contentY")) == 0.0, "the week moved after Month"


def test_a_new_text_size_leaves_the_week_where_the_student_scrolled_it(qapp, window) -> None:
    root = _opened(window, qapp)
    scroller = _scroller(root)
    _away(qapp, scroller)
    with _text_size(window, qapp, "large"):
        assert float(_scroller(root).property("contentY")) == 0.0, "a new text size moved the week"


def test_today_brings_now_back_after_the_student_scrolled_away(qapp, window) -> None:
    root = _opened(window, qapp)
    scroller = _scroller(root)
    _away(qapp, scroller)
    assert not _in_view(_named(root, "nowLine")[0], scroller)
    _turn(qapp, window, "today")
    assert _in_view(_named(root, "nowLine")[0], _scroller(root)), "Today left now out of view"


def test_a_new_text_size_keeps_the_time_at_the_top_of_the_week(qapp, window) -> None:
    """The row grows with the text, so the same distance down is an earlier time: the place is the time."""
    root = _opened(window, qapp)
    scroller = _scroller(root)
    row = float(_bridge(window).property("hourRow"))
    scroller.setProperty("contentY", 3 * row)
    _pump(qapp, 20)
    with _text_size(window, qapp, "large"):
        grown = float(_bridge(window).property("hourRow"))
        assert grown > row, "the text size did not change the row, so the test says nothing"
        assert float(_scroller(root).property("contentY")) == pytest.approx(3 * grown, abs=2)
