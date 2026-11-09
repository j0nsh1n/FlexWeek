"""The Material week's homework queue: Plan places it and Undo puts it back, the tags that say how
much room each piece has, dragging a card to the grid, and giving a card a time from the keyboard.
Expected values come from the spec and from the account's own data, not from what the QML prints.
How the disabled Plan button and the dropped block look is a picture (pictures/week_material.py)."""

# ruff: noqa: F811
from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest

from desktop.native.material.bridge_week import SLACK_TAGS, WeekBridge
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import (
    NOW_DAY,
    _block_named,
    _bridge,
    _centre,
    _click,
    _drag,
    _homework,
    _named,
    _pump,
    _qml,
    _repeater_texts,
    _reset,
    _snack,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401


def test_plan_places_the_queue_and_undo_puts_it_back(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "poster", "Science poster", 60, due)
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    _pump(qapp)
    plan = _qml(root, "planHomework")
    assert _qml(root, "homeworkCount").property("text") == "2"
    assert plan.property("enabled") is True
    waiting_before = {
        block["id"] for block in window.session.blocks if block.get("assignment_id") in ("poster", "sheet")
    }
    assert all(not block.get("start") for block in window.session.blocks if block["id"] in waiting_before)

    _click(window, plan)
    wait_until(qapp, lambda: _snack(window).startswith("Placed") and not window.session.busy)

    assert _snack(window) == "Placed 2 of 2"
    assert _qml(root, "homeworkCount").property("text") == "0"
    assert _qml(root, "homeworkEmptyText").property("text") == "Everything has a time."
    assert _qml(root, "homeworkEmpty").property("visible") is True
    titles = _repeater_texts(root, "weekBlocks", "title")
    assert "Science poster" in titles
    assert "Math worksheet" in titles
    placed = [block for block in window.session.blocks if block["id"] in waiting_before]
    assert all(block.get("start") for block in placed)

    # With nothing left to place the button is a text button and a click does nothing.
    plan = _qml(root, "planHomework")
    assert plan.property("enabled") is False
    assert plan.property("kind") == "text"
    note = _snack(window)
    _click(window, plan)
    assert _snack(window) == note

    # UNDO on the snackbar restores the queue and turns the button back on.
    bar = _qml(root, "materialSnackbar")
    _click(window, bar, dx=int(bar.property("width")) // 2 - 30)
    wait_until(
        qapp,
        lambda: not window.session.busy and _qml(root, "homeworkCount").property("text") == "2",
    )
    assert _qml(root, "planHomework").property("enabled") is True
    assert _qml(root, "homeworkEmpty").property("visible") is False
    assert _snack(window) == ""
    after = [block for block in window.session.blocks if block["id"] in waiting_before]
    assert all(not block.get("start") for block in after)
    texts = _repeater_texts(root, "homeworkRows", "homeworkTitle")
    assert sorted(texts) == ["Math worksheet", "Science poster"]


def test_the_top_bar_undo_also_restores_a_plan(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "poster", "Science poster", 60, due)
    settled(qapp, window)
    _pump(qapp)
    _click(window, _qml(root, "planHomework"))
    wait_until(qapp, lambda: _snack(window).startswith("Placed") and not window.session.busy)
    _pump(qapp)
    assert _qml(root, "homeworkCount").property("text") == "0"
    _click(window, _qml(root, "materialUndo"))
    wait_until(qapp, lambda: not window.session.busy and _qml(root, "homeworkCount").property("text") == "1")
    assert _qml(root, "planHomework").property("enabled") is True


def test_a_same_day_spread_says_so_in_the_snackbar(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    window.session.add_homework(
        {
            "id": "spread-essay",
            "title": "History essay",
            "due": due,
            "estimate_min": 90,
            "revision": 0,
        },
        spread=True,
    )
    for key, minutes in (("spread-a", 60), ("spread-b", 30)):
        window.session.add_block(
            {
                "id": key,
                "title": "History essay",
                "kind": "flexible",
                "duration_min": minutes,
                "days": [4],
                "priority": 3,
                "energy": "medium",
                "assignment_id": "spread-essay",
            }
        )
    window.session.save()
    settled(qapp, window)
    _pump(qapp)
    window._material_page.publish()
    _pump(qapp)
    _click(window, _qml(root, "planHomework"))
    note = "Couldn't spread History essay over separate days, so two parts share Friday."
    wait_until(qapp, lambda: note in _snack(window) and not window.session.busy)
    assert note in _snack(window)


def test_plan_is_disabled_when_nothing_needs_a_time(qapp, window) -> None:
    root = _reset(window, qapp)
    assert _qml(root, "homeworkCount").property("text") == "0"
    assert _qml(root, "planHomework").property("enabled") is False
    assert _qml(root, "homeworkEmptyText").property("text") == "Everything has a time."
    assert _qml(root, "homeworkHeading").property("text") == "No time yet · drag onto a day"


def test_plenty_of_time_is_never_due_within_24_hours() -> None:
    start = date(2026, 11, 2)
    moment = datetime(2026, 11, 5, 19, 0)
    soon = SimpleNamespace(due="2026-11-06T18:00", minutes=30)
    later = SimpleNamespace(due="2026-11-06T20:00", minutes=30)
    assert WeekBridge._tag_for(soon, start, moment) == SLACK_TAGS["tight"]
    assert WeekBridge._tag_for(later, start, moment) == SLACK_TAGS["ok"]


def test_an_all_day_due_is_tight_five_hours_before_midnight() -> None:
    start = date(2026, 11, 2)
    assert (
        WeekBridge._tag_for(
            SimpleNamespace(due="2026-11-06", minutes=30), start, datetime(2026, 11, 6, 19, 0)
        )
        == SLACK_TAGS["tight"]
    )
    assert (
        WeekBridge._tag_for(
            SimpleNamespace(due="2026-11-06T23:59", minutes=30), start, datetime(2026, 11, 6, 0, 0)
        )
        == SLACK_TAGS["ok"]
    )


def test_plenty_applies_after_this_weeks_sunday() -> None:
    start = date(2026, 11, 2)
    moment = datetime(2026, 11, 8, 19, 0)
    soon = SimpleNamespace(due="2026-11-09T18:00", minutes=30)
    later = SimpleNamespace(due="2026-11-09T20:00", minutes=30)
    assert WeekBridge._tag_for(soon, start, moment) == SLACK_TAGS["tight"]
    assert WeekBridge._tag_for(later, start, moment) == SLACK_TAGS["ok"]


def test_status_tags_say_plenty_is_tight_when_due_within_24_hours(qapp, window) -> None:
    root = _reset(window, qapp)
    friday = (_week_monday(window) + timedelta(days=4)).isoformat()
    _homework(window, "soon", "Due soon", 30, f"{friday}T18:00")
    _homework(window, "later", "Due later", 30, f"{friday}T20:00")
    settled(qapp, window)
    _pump(qapp)
    found = {}
    for card in _named(root, "homeworkCard"):
        title = next((str(item.property("text")) for item in _named(card, "homeworkTitle")), "")
        tag = next(
            (str(item.property("text")) for item in _named(card, "homeworkTag") if item.property("visible")),
            "",
        )
        if title:
            found[title] = tag
    assert found.get("Due soon") == "Tight"
    assert found.get("Due later") == "Plenty of time"


def test_status_tags_say_how_much_room_the_homework_has(qapp, window) -> None:
    """Clock is Thursday 19:00. Room is time until due minus the time the homework needs."""
    root = _reset(window, qapp)
    monday = _week_monday(window)
    thursday = (monday + timedelta(days=NOW_DAY)).isoformat()
    _homework(window, "cut", "Cut one", 60, f"{thursday}T21:00")  # 120 - 60 = 60 min: cutting it close
    _homework(window, "tight", "Tight one", 30, f"{thursday}T22:00")  # 180 - 30 = 150 min: tight
    _homework(window, "plenty", "Plenty one", 30, (monday + timedelta(days=6)).isoformat())
    settled(qapp, window)
    _pump(qapp)
    tags = {str(card_title.property("text")): "" for card_title in _named(root, "homeworkTitle")}
    assert set(tags) == {"Cut one", "Tight one", "Plenty one"}
    said = sorted(str(tag.property("text")) for tag in _named(root, "homeworkTag") if tag.property("visible"))
    assert said == ["Cutting it close", "Plenty of time", "Tight"]
    details = sorted(_repeater_texts(root, "homeworkRows", "homeworkDetail"))
    sunday = monday + timedelta(days=6)
    # A length keeps its unit on the same line (non-breaking space), so a narrow card never leaves "h" alone.
    assert details == sorted(
        [
            f"Due Thu {(monday + timedelta(days=NOW_DAY)).day} "
            f"{(monday + timedelta(days=NOW_DAY)).strftime('%b')}, 21:00 · 1\u00a0h",
            f"Due Thu {(monday + timedelta(days=NOW_DAY)).day} "
            f"{(monday + timedelta(days=NOW_DAY)).strftime('%b')}, 22:00 · 30\u00a0min",
            f"Due Sun {sunday.day} {sunday.strftime('%b')} · 30\u00a0min",
        ]
    )


def test_dragging_a_card_onto_the_grid_gives_it_the_time_under_the_pointer(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    _pump(qapp)
    card = _named(root, "homeworkCard")[0]
    grid = _qml(root, "weekScroller")
    hours_item = next(child for child in grid.childItems()[0].childItems() if child.property("width"))
    row = int(_bridge(window).property("hourRow"))
    gutter = int(_qml(root, "materialWeek").property("gutter"))
    day_width = float(_qml(root, "materialWeek").property("dayWidth"))
    friday = 4
    grid.setProperty("contentY", float(16 * row - 100))
    _pump(qapp)
    # Let go two pixels past 16:15 on Friday: in the default 5-minute step the nearest is 16:15, so
    # the card lands there, not on the hour (recheck M3: a 16:15 drop landed at 16:00).
    inside = hours_item.mapToScene(QPointF(gutter + friday * day_width + day_width / 2, 16.25 * row + 2))
    _drag(window, card, QPoint(int(inside.x()), int(inside.y())))
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    placed = next(block for block in window.session.blocks if block.get("assignment_id") == "sheet")
    assert placed["start"] == "16:15"
    assert placed["days"] == [friday]
    _pump(qapp)
    assert _qml(root, "homeworkCount").property("text") == "0"
    assert _block_named(root, "Math worksheet") is not None
    # The active Material snackbar is the only presenter; the Widgets toast stays hidden.
    assert "Math worksheet" in _snack(window)
    assert window.toast.isHidden()
    assert _qml(root, "materialSnackbar").property("actionText") == "UNDO"


def test_a_drop_off_the_grid_changes_nothing(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    _pump(qapp)
    card = _named(root, "homeworkCard")[0]
    _drag(window, card, QPoint(_centre(root, card).x(), _centre(root, card).y() + 6))
    wait_until(qapp, lambda: not window.session.busy)
    still = next(block for block in window.session.blocks if block.get("assignment_id") == "sheet")
    assert not still.get("start")
    assert _qml(root, "homeworkCount").property("text") == "1"


def test_a_card_can_be_given_a_time_from_the_keyboard(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    _pump(qapp)
    card = _named(root, "homeworkCard")[0]
    assert card.property("activeFocusOnTab") is True
    card.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    _pump(qapp)
    menu = _named(root, "cardMenu")[0]
    assert menu.property("open") is True
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Down)
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
    wait_until(qapp, lambda: not window.session.busy and _qml(root, "homeworkCount").property("text") == "0")
    placed = next(block for block in window.session.blocks if block.get("assignment_id") == "sheet")
    assert placed.get("start")


def test_blocks_that_just_landed_are_marked_fresh_once(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    _pump(qapp)
    _click(window, _qml(root, "planHomework"))
    wait_until(qapp, lambda: _snack(window).startswith("Placed") and not window.session.busy)
    _pump(qapp)
    rows = _bridge(window).property("week").property("blockRows")
    fresh = [row["title"] for row in rows if row["fresh"]]
    assert fresh == ["Math worksheet"]


def test_tabbing_through_homework_cards_keeps_the_focused_card_in_view(qapp, window) -> None:
    root = _reset(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    for index in range(18):
        _homework(window, f"card-{index}", f"Card {index:02}", 30, due)
    _pump(qapp)
    cards = _named(root, "homeworkCard")
    assert len(cards) == 18
    scroller = _qml(root, "homeworkScroller")
    quick = window._material_page._quick
    cards[0].forceActiveFocus()
    _pump(qapp)
    for card in cards:
        assert card.property("activeFocus") is True
        top = card.mapToScene(QPointF(0, 0)).y()
        bottom = card.mapToScene(QPointF(0, card.property("height"))).y()
        view_top = scroller.mapToScene(QPointF(0, 0)).y()
        view_bottom = scroller.mapToScene(QPointF(0, scroller.property("height"))).y()
        assert top >= view_top - 1, (card.property("title"), top, view_top)
        assert bottom <= view_bottom + 1, (card.property("title"), bottom, view_bottom)
        QTest.keyClick(quick, Qt.Key.Key_Tab)
        _pump(qapp)
