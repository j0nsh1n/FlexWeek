"""The Material week's grid: finishing a homework block, fixed blocks, what the clock dims, the
weekend columns, row density, the clock in the labels, the day headers and moving between weeks.
How the dimming, column widths, row heights and today marker look is a picture
(pictures/week_material.py)."""

# ruff: noqa: F811
from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPointF, QRectF, Qt
from PySide6.QtGui import QAccessible, QFontMetricsF
from PySide6.QtTest import QTest

from desktop.native.weekmodel import clock_label
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import (
    NOW_DAY,
    _block_named,
    _bridge,
    _click,
    _give_the_essay_two_lines,
    _homework,
    _look,
    _named,
    _pref,
    _pump,
    _qml,
    _repeater_texts,
    _reset,
    _show_material,
    _snack,
    _text_size,
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


def test_a_default_one_hour_homework_in_week_has_its_done_circle_in_its_corner_off_the_title(
    qapp, window
) -> None:
    """Jonathan, 2026-11-08 (option A): when the circle on the title row would cut the title, it sits in
    the block's bottom-right corner instead of hiding, never over the title, and still finishes the
    homework on a click and takes Tab."""
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    work = next(b for b in window.session.blocks if b.get("assignment_id") == "essay")
    assert work["duration_min"] == 60
    finish = _named(essay, "weekBlockFinish")[0]
    assert finish.property("visible") is True
    block, circle = _rect(essay), _rect(finish)
    assert block.contains(circle)
    assert circle.width() >= 20 and circle.height() >= 20
    assert circle.center().x() > block.center().x() and circle.center().y() > block.center().y()
    assert not circle.intersects(_rect(_named(essay, "title")[0]))
    for detail in _named(essay, "detail"):
        if detail.property("visible"):
            assert not circle.intersects(_rect(detail))

    quick = window._material_page._quick
    essay.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Tab)
    _pump(qapp)
    assert finish.property("activeFocus") is True

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


def test_in_week_a_fixed_block_opens_on_click_and_enter_and_is_a_tab_stop(qapp, window) -> None:
    # Jonathan, 2026-11-08: in Week, School and activities open on click and Enter and take Tab, as
    # they do in Day.
    root = _reset(window, qapp)
    sheets = window._material_page.bridge.sheets
    quick = window._material_page._quick
    row = int(_bridge(window).property("hourRow"))
    _qml(root, "weekScroller").setProperty("contentY", float(8 * row))
    _pump(qapp, 4)
    schools = sorted(
        (block for block in _named(root, "weekBlock") if block.property("title") == "School"),
        key=lambda block: block.mapToScene(QPointF(0, 0)).x(),
    )
    assert len(schools) == 5
    try:
        _click(window, schools[0])
        assert (sheets.kind, sheets.form["title"]) == ("block", "School")
        sheets.forceClose()
        _pump(qapp)

        schools[0].forceActiveFocus()
        _pump(qapp)
        QTest.keyClick(quick, Qt.Key.Key_Return)
        _pump(qapp)
        assert (sheets.kind, sheets.form["title"]) == ("block", "School")
        sheets.forceClose()
        _pump(qapp)

        # Tab runs in time order through the week: Thursday's School comes just before the essay that
        # evening.
        essay = _block_named(root, "History essay")
        essay.forceActiveFocus()
        _pump(qapp)
        QTest.keyClick(quick, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        _pump(qapp)
        assert schools[NOW_DAY].property("activeFocus") is True
    finally:
        sheets.forceClose()
        _pump(qapp)


def _rect(item: QObject) -> QRectF:
    return item.mapRectToScene(item.boundingRect())


def _pin_on_thursday(window, qapp, key: str, title: str, start: str, minutes: int) -> None:
    session = window.session
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, key, title, minutes, due)
    work = next(block for block in session.blocks if block.get("assignment_id") == key)
    work.update({"start": start, "days": [NOW_DAY], "duration_min": minutes, "pinned": True})
    session.add_block(work)
    session.save()
    settled(qapp, window)
    _pump(qapp)


def _a_title_the_circle_would_cut(block: QObject) -> str:
    """Two words that each fit the whole title column of a lone Week block (its width less 12 px and
    8 px padding) but not the column a circle on the title row leaves (28 px less): beside the circle
    the title needs more than its two lines and is cut."""
    metrics = QFontMetricsF(_named(block, "title")[0].property("font"))
    width = float(block.property("width"))
    whole, beside = width - 20, width - 48
    words = [
        "Algebra",
        "Biology",
        "Chemistry",
        "Geography",
        "Literature",
        "Vocabulary",
        "Mathematics",
        "Trigonometry",
        "Shakespeare",
        "Photosynthesis",
    ]
    fit = [word for word in words if beside + 4 < metrics.horizontalAdvance(word) < whole - 4]
    assert len(fit) >= 2, (width, {word: metrics.horizontalAdvance(word) for word in words})
    return f"{fit[0]} {fit[1]}"


def _time_line(block: QObject) -> str:
    """The words of the block's time line as the student reads them, "" when it is not shown."""
    for detail in _named(block, "detail"):
        if detail.property("visible"):
            return str(detail.property("text"))
    return ""


def test_a_one_hour_homework_at_large_text_shows_its_start_only_beside_the_corner_circle(
    qapp, window
) -> None:
    """Jonathan, 2026-11-08 (option 1): where the corner circle sits beside the time line and the range
    does not fit beside it, the line reads "18:45", never "18:45-..."."""
    root = _reset(window, qapp)
    with _text_size(window, qapp, "large"):
        essay = _block_named(root, "History essay")
        finish = _named(essay, "weekBlockFinish")[0]
        assert finish.property("visible") is True
        assert essay.property("circleBesideTime") is True
        assert _time_line(essay) == "18:45"
        detail = next(d for d in _named(essay, "detail") if d.property("visible"))
        assert detail.property("truncated") is False


def test_a_time_line_keeps_its_whole_range_where_it_fits_or_the_circle_is_not_beside_it(qapp, window) -> None:
    root = _reset(window, qapp)
    # The ordinary one-hour essay at Normal text, 1280 px, 24-hour clock: the circle is beside the line
    # and the whole range still fits beside it, so the range stays (the start alone is for when it does not).
    plain = _block_named(root, "History essay")
    assert _named(plain, "weekBlockFinish")[0].property("visible") is True
    assert plain.property("circleBesideTime") is True
    assert _time_line(plain) == "18:45\u201319:45"

    # 90 minutes at Normal text: the circle stays on the title row, the line has the whole width.
    _give_the_essay_two_lines(window, qapp)
    essay = _block_named(root, "History essay")
    assert _time_line(essay) == "18:45\u201320:15"

    # A tall block whose circle sits below the time line: the circle takes nothing from the line.
    row = int(_bridge(window).property("hourRow"))
    _qml(root, "weekScroller").setProperty("contentY", float(14 * row))
    _pump(qapp, 4)
    title = _a_title_the_circle_would_cut(essay)
    _pin_on_thursday(window, qapp, "long", title, "15:00", 120)
    long = _block_named(root, title)
    assert long.property("circleCorner") is True
    assert _named(long, "weekBlockFinish")[0].property("visible") is True
    assert long.property("circleBesideTime") is False
    assert _time_line(long) == "15:00\u201317:00"


def test_the_start_only_time_line_is_still_read_out_whole(qapp, window) -> None:
    root = _reset(window, qapp)
    with _text_size(window, qapp, "large"):
        essay = _block_named(root, "History essay")
        assert _time_line(essay) == "18:45"
        name = QAccessible.queryAccessibleInterface(essay).text(QAccessible.Text.Name)
        assert name == "Edit History essay, 18:45\u201319:45"


def test_a_homework_block_that_shares_no_time_moves_or_hides_its_circle_rather_than_cut_its_title(
    qapp, window
) -> None:
    """Jonathan, 2026-11-08: the done-circle rule holds for every Week block, not only blocks that share
    time. When the circle on the title row would cut the title, it moves to the block's corner, or hides
    on a block too short for that, where the menu still finishes the homework."""
    root = _reset(window, qapp)
    row = int(_bridge(window).property("hourRow"))
    _qml(root, "weekScroller").setProperty("contentY", float(14 * row))
    _pump(qapp, 4)
    title = _a_title_the_circle_would_cut(_block_named(root, "History essay"))
    short_title = title + " notes"
    # Thursday 15:00 to 17:00 and 17:30 to 18:00: after School, before the essay at 18:45.
    _pin_on_thursday(window, qapp, "long", title, "15:00", 120)
    _pin_on_thursday(window, qapp, "short", short_title, "17:30", 30)
    rows = _bridge(window).property("week").property("blockRows")
    for name in (title, short_title):
        mine = next(r for r in rows if r["title"] == name)
        assert (mine["day"], mine["indent"], list(mine["under"])) == (NOW_DAY, 0, []), name
    for name in (title, short_title):
        assert all(r["title"] != name for r in rows if r["day"] == NOW_DAY and list(r["under"]))

    long = _block_named(root, title)
    long_title, finish = _named(long, "title")[0], _named(long, "weekBlockFinish")[0]
    assert long_title.property("truncated") is False
    assert finish.property("visible") is True
    assert _rect(long).contains(_rect(finish))
    assert not _rect(finish).intersects(_rect(long_title))
    _click(window, finish)
    wait_until(
        qapp, lambda: not window.session.busy and bool(window.session.assignments["long"].get("completed"))
    )

    short = _block_named(root, short_title)
    short_finish = _named(short, "weekBlockFinish")[0]
    assert short_finish.property("visible") is False
    assert short_finish.property("activeFocusOnTab") is False
    quick = window._material_page._quick
    menu = _named(root, "blockMenu")[0]
    short.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    _pump(qapp)
    try:
        assert menu.property("open") is True
        assert "Mark finished" in [e["label"] for e in menu.property("entries").toVariant()]
    finally:
        QTest.keyClick(quick, Qt.Key.Key_Escape)
        _pump(qapp)


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


def test_on_the_12_hour_clock_the_start_only_line_reads_6_45_pm_where_the_range_does_not_fit(
    qapp, window
) -> None:
    """The one-hour essay at Normal text and 1280 px on the 12-hour clock: the line beside the circle is
    about 62 px, the range "6:45\u20137:45 PM" is wider, "6:45 PM" fits whole."""
    root = _reset(window, qapp)
    _pref(window, clock_24h=False)
    window._material_page.publish()
    _pump(qapp)
    essay = _block_named(root, "History essay")
    assert _named(essay, "weekBlockFinish")[0].property("visible") is True
    assert essay.property("circleBesideTime") is True
    assert _time_line(essay) == "6:45 PM"
    detail = next(d for d in _named(essay, "detail") if d.property("visible"))
    assert detail.property("truncated") is False
    name = QAccessible.queryAccessibleInterface(essay).text(QAccessible.Text.Name)
    assert name == "Edit History essay, 6:45\u20137:45 PM"


def test_where_even_the_start_would_be_cut_beside_the_corner_circle_the_circle_hides(qapp, window) -> None:
    """Jonathan, 2026-11-09 (option 1): on the 12-hour clock in a 1050 px window the one-hour essay's line
    beside the corner circle is narrower than "6:45 PM", so the circle hides and the line takes the whole
    width, still the start alone where the range does not fit. Edit and the menu still finish it."""
    root = _reset(window, qapp)
    _pref(window, clock_24h=False)
    window._material_page.publish()
    _pump(qapp)
    window.resize(1050, 800)
    _pump(qapp, 6)
    try:
        essay = _block_named(root, "History essay")
        content = next(c for c in essay.childItems() if c.property("lineRoom") is not None)
        beside = float(content.property("lineRoom")) - float(essay.property("cornerSize")) - 8
        assert essay.property("circleCorner") is True
        assert float(content.property("startWidth")) > beside
        assert essay.property("circleWouldCutStart") is True
        assert _named(essay, "weekBlockFinish")[0].property("visible") is False
        assert essay.property("circleBesideTime") is False
        detail = next(d for d in _named(essay, "detail") if d.property("visible"))
        assert detail.property("truncated") is False
        assert float(detail.property("width")) == float(content.property("lineRoom"))
        # About 57 px of line: the range does not fit even the whole width, so the start alone shows.
        assert _time_line(essay) == "6:45 PM"
        name = QAccessible.queryAccessibleInterface(essay).text(QAccessible.Text.Name)
        assert name == "Edit History essay, 6:45\u20137:45 PM"
    finally:
        window.resize(1280, 800)
        _pump(qapp, 6)


def _soccer_with_three_homeworks_over_it(window, qapp) -> None:
    """Jonathan's footage of 2026-11-09: Soccer 16:00-17:30 on Thursday with three homework blocks over
    it, the last one 16:50, so the later blocks are squeezed narrow by the stack."""
    session = window.session
    session.add_block(
        {
            "id": "soccer",
            "title": "Soccer",
            "kind": "locked",
            "category": "exercise",
            "start": "16:00",
            "duration_min": 90,
            "days": [NOW_DAY],
        }
    )
    session.save()
    settled(qapp, window)
    _pin_on_thursday(window, qapp, "read", "Read chapter", "16:00", 60)
    _pin_on_thursday(window, qapp, "poster", "Science poster", "16:00", 60)
    _pin_on_thursday(window, qapp, "math", "Math worksheet", "16:50", 60)


def _every_time_line_is_whole_or_the_start_alone(root: QObject) -> dict[str, str]:
    """Jonathan, 2026-11-09: a time line is never cut part-way. Each Week block shows its whole range,
    the start alone, or no line; returns what each block shows ("" for no line)."""
    shown = {}
    for block in _named(root, "weekBlock"):
        name = str(block.property("title"))
        line = _time_line(block)
        shown[name] = line
        if line == "":
            continue
        assert line in (block.property("detail"), block.property("detailStart")), (name, line)
        detail = next(d for d in _named(block, "detail") if d.property("visible"))
        assert detail.property("truncated") is False, (name, line)
        assert float(detail.property("contentWidth")) <= float(detail.property("width")), (name, line)
    return shown


def test_a_squeezed_blocks_time_line_is_the_start_alone_or_gone_never_cut_part_way(qapp, window) -> None:
    root = _reset(window, qapp)
    _pref(window, clock_24h=False)
    window._material_page.publish()
    _pump(qapp)
    _soccer_with_three_homeworks_over_it(window, qapp)
    shown = _every_time_line_is_whole_or_the_start_alone(root)
    narrow = shown["Math worksheet"]
    assert narrow in ("", "4:50 PM"), shown
    # The stack really squeezes a block until its range cannot fit, so the check above is not vacuous.
    whole = _block_named(root, "Math worksheet").property("detail")
    assert narrow != whole, shown


def test_in_a_narrow_window_at_larger_text_no_time_line_is_cut_part_way(qapp, window) -> None:
    root = _reset(window, qapp)
    _pref(window, clock_24h=False)
    window._material_page.publish()
    _pump(qapp)
    _soccer_with_three_homeworks_over_it(window, qapp)
    window.resize(1050, 800)
    _pump(qapp, 6)
    try:
        with _text_size(window, qapp, "larger"):
            shown = _every_time_line_is_whole_or_the_start_alone(root)
            assert any(line == "" or "–" not in line for line in shown.values()), shown
    finally:
        window.resize(1280, 800)
        _pump(qapp, 6)
