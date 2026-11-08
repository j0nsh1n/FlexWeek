"""The Material week's grid: finishing a homework block, fixed blocks, what the clock dims, the
weekend columns, row density, the clock in the labels, the day headers and moving between weeks.
How the dimming, column widths, row heights and today marker look is a picture
(pictures/week_material.py)."""

# ruff: noqa: F811
from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from desktop.native.weekmodel import clock_label
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import (
    NOW_DAY,
    _block_named,
    _bridge,
    _click,
    _look,
    _named,
    _pref,
    _pump,
    _qml,
    _repeater_texts,
    _reset,
    _show_material,
    _snack,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import look_file, qapp, settled  # noqa: F401


def test_clicking_homework_finishes_it_and_undo_opens_it_again(qapp, window) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    assert essay.property("homework") is True
    assert window.session.assignments["essay"].get("completed") in (None, False)
    finish = _named(essay, "weekBlockFinish")[0]
    _click(window, finish)
    wait_until(
        qapp, lambda: not window.session.busy and bool(window.session.assignments["essay"].get("completed"))
    )
    wait_until(qapp, lambda: _snack(window) == "Finished History essay.")
    _pump(qapp)
    assert _block_named(root, "History essay").property("done") is True
    bar = _qml(root, "materialSnackbar")
    _click(window, bar, dx=int(bar.property("width")) // 2 - 30)
    wait_until(
        qapp,
        lambda: not window.session.busy and not window.session.assignments["essay"].get("completed"),
    )
    _pump(qapp)
    assert _block_named(root, "History essay").property("done") is False


def test_a_fixed_block_is_not_a_button(qapp, window) -> None:
    root = _reset(window, qapp)
    school = _block_named(root, "School")
    assert school.property("homework") is False
    assert school.property("activeFocusOnTab") is False
    _click(window, school)
    _pump(qapp)
    assert _snack(window) == ""


def test_past_blocks_are_marked_by_the_clock(qapp, window) -> None:
    """Thursday 19:00: School is over Monday to Thursday, Friday is ahead, the essay is under way."""
    root = _reset(window, qapp)
    rows = _bridge(window).property("week").property("blockRows")
    school_past = {row["day"]: row["past"] for row in rows if row["title"] == "School"}
    assert school_past == {0: True, 1: True, 2: True, 3: True, 4: False}
    schools = [block for block in _named(root, "weekBlock") if block.property("title") == "School"]
    assert sorted(bool(block.property("past")) for block in schools) == [False, True, True, True, True]
    assert _block_named(root, "History essay").property("past") is False

    _pref(window, dim_completed=False)
    window._material_page.publish()
    _pump(qapp)
    for block in _named(root, "weekBlock"):
        assert block.property("past") is False


def test_a_week_that_is_over_is_all_past_and_one_ahead_is_not(qapp, window) -> None:
    root = _reset(window, qapp)
    session = window.session
    home = _week_monday(window)
    for offset, expected in ((-7, True), (14, False)):
        session.load_week((home + timedelta(days=offset)).isoformat())
        settled(qapp, window)
        session.add_block(
            {
                "id": f"visit{offset}",
                "title": "Dentist",
                "kind": "locked",
                "category": "extra",
                "start": "10:00",
                "duration_min": 60,
                "days": [2],
            }
        )
        session.save()
        settled(qapp, window)
        window._material_page.publish()
        _pump(qapp)
        visit = _block_named(root, "Dentist")
        assert visit.property("past") is expected, offset


def test_weekends_off_gives_five_columns_and_takes_the_weekend_blocks_away(qapp, window) -> None:
    root = _reset(window, qapp)
    session = window.session
    session.add_block(
        {
            "id": "sat",
            "title": "Match",
            "kind": "locked",
            "category": "extra",
            "start": "10:00",
            "duration_min": 60,
            "days": [5],
        }
    )
    session.save()
    settled(qapp, window)
    window._material_page.publish()
    _pump(qapp)
    assert len(_named(root, "dayHeader")) == 7
    assert "Match" in _repeater_texts(root, "weekBlocks", "title")

    _pref(window, show_weekends=False)
    window._material_page.publish()
    _pump(qapp)
    assert len(_named(root, "dayHeader")) == 5
    names = [str(label.property("text")) for label in _named(root, "dayHeader")]
    assert not any(name.startswith(("Sat", "Sun")) for name in names)
    assert "Match" not in _repeater_texts(root, "weekBlocks", "title")

    _pref(window, show_weekends=True)
    window._material_page.publish()
    _pump(qapp)
    assert len(_named(root, "dayHeader")) == 7
    assert "Match" in _repeater_texts(root, "weekBlocks", "title")


def test_a_missing_weekend_preference_reads_as_seven_columns(qapp, window) -> None:
    root = _reset(window, qapp)
    prefs = dict(window.session.preferences or {})
    prefs.pop("show_weekends", None)
    window.session.preferences = prefs
    window._material_page.publish()
    _pump(qapp)
    assert len(_named(root, "dayHeader")) == 7


def test_compact_density_shortens_the_hour_rows_to_44(qapp, window) -> None:
    _reset(window, qapp)
    assert int(_bridge(window).property("hourRow")) == 56
    _look(window, density="compact")
    _show_material(qapp, window)
    assert int(_bridge(window).property("hourRow")) == 44
    look_file().unlink(missing_ok=True)
    window._material_page.publish()


def test_hour_labels_follow_the_accounts_clock(qapp, window) -> None:
    root = _reset(window, qapp)
    labels = _repeater_texts(root, "hourLabels", "hourLabel")
    assert labels[13] == "13:00"
    assert labels[13] == clock_label(13 * 60)
    _pref(window, clock_24h=False)
    window._material_page.publish()
    _pump(qapp)
    labels = _repeater_texts(root, "hourLabels", "hourLabel")
    assert labels[13] != "13:00"
    assert "PM" in labels[13].upper()
    assert _qml(root, "materialClock").property("text") == "7:00 PM"
    detail = [str(text.property("text")) for text in _named(_block_named(root, "History essay"), "detail")]
    assert detail
    assert "PM" in detail[0].upper()


def test_the_day_headers_mark_today_and_carry_the_dates(qapp, window) -> None:
    root = _reset(window, qapp)
    monday = _week_monday(window)
    texts = _repeater_texts(root, "dayHeaders", "dayHeader")
    assert texts == [
        f"{name} {(monday + timedelta(days=index)).day}"
        for index, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
    ]
    headers = _named(root, "dayHeader")
    assert [bool(header.property("today")) for header in headers] == [index == NOW_DAY for index in range(7)]


def test_the_top_bar_moves_the_week_and_today_comes_back(qapp, window) -> None:
    root = _reset(window, qapp)
    home = window.session.week_start
    _click(window, _qml(root, "weekNext"))
    wait_until(qapp, lambda: window.session.week_start != home and not window.session.busy)
    assert window.session.week_start == (date.fromisoformat(home) + timedelta(days=7)).isoformat()
    _click(window, _qml(root, "weekPrevious"))
    _click(window, _qml(root, "weekPrevious"))
    wait_until(
        qapp, lambda: window.session.week_start == (date.fromisoformat(home) - timedelta(days=7)).isoformat()
    )
    _click(window, _qml(root, "weekToday"))
    wait_until(qapp, lambda: window.session.week_start == home)
    for name in ("weekPrevious", "weekToday", "weekNext"):
        assert _qml(root, name).property("visible") is True
    _bridge(window).showPage("settings")
    _pump(qapp)
    assert _qml(root, "weekToday").property("visible") is False
    _bridge(window).showPage("week")


def test_the_now_line_passes_behind_blocks_and_the_dot_stays_on_top(qapp, window) -> None:
    """The now line sits under every week block and the left dot above; a homework held over a slot
    outlines it above the line. How they look where they cross is judged in the picture review."""
    root = _reset(window, qapp)
    line_z = float(_qml(root, "nowLine").property("z"))
    dot_z = float(_qml(root, "nowDot").property("z"))
    blocks = _named(root, "weekBlock")
    assert blocks
    for block in blocks:
        block_z = float(block.property("z"))
        assert line_z < block_z, (line_z, block_z)
        assert dot_z > block_z, (dot_z, block_z)
    assert float(_qml(root, "dropSlot").property("z")) > line_z
