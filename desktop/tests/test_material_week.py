"""The Material week: plan, undo, drag, finish, dim, weekend columns, compact rows, navigation.

Expected values come from the spec (Jonathan's section 3 and the approved mockup) and from
the account's own data, not from reading what the QML prints.
"""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Iterator
from datetime import date, datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, QStandardPaths, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop.native.weekmodel import clock_label, set_clock_24h  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.server import LocalServer  # noqa: E402
from desktop.tests.logic_support import past_setup  # noqa: E402
from desktop.tests.test_layouts_window import (  # noqa: E402
    PASSWORD,
    look_file,
    settled,
    wait_until,
)
from desktop.tests.test_material_window import (  # noqa: E402
    _named,
    _pump,
    _qml,
    _repeater_texts,
    _show_material,
)

WIDTH = 1280
# Thursday 19:00 of the week the account opens on.
NOW_DAY = 3
NOW_MINUTE = 19 * 60


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-material-week"])
    yield application


def _pref(window: NativeWindow, **values: object) -> None:
    window.session.preferences = {**(window.session.preferences or {}), **values}


def _look(window: NativeWindow, **material: str) -> None:
    """Write the Material look the way the look file keeps it, and publish it."""
    path = look_file()
    stored = json.loads(path.read_text()) if path.exists() else {}
    stored["material"] = {**stored.get("material", {}), **material}
    path.write_text(json.dumps(stored))
    window._material_page.publish()
    _pump(QApplication.instance())


@pytest.fixture(scope="module")
def window(qapp: QApplication, tmp_path_factory: pytest.TempPathFactory) -> Iterator[NativeWindow]:
    """Signed in, clock held at Thursday 19:00, School Monday to Thursday mornings, the History
    essay planned for 18:45 that day, and nothing else placed."""
    look_file().unlink(missing_ok=True)
    server = LocalServer(tmp_path_factory.mktemp("material-week") / "flexweek.db")
    server.start()
    made = NativeWindow(server.origin)
    made.show()
    made.resize(WIDTH, 800)
    try:
        made.username.setText("material_week")
        made.password.setText(PASSWORD)
        made.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "recoveryPage")
        made.recovery_ack.setChecked(True)
        made.recovery_continue.click()
        past_setup(qapp, made)
        wait_until(qapp, lambda: made.session.preferences is not None)
        session = made.session
        made.home_week = session.week_start
        thursday = datetime.fromisoformat(session.week_start) + timedelta(days=NOW_DAY, hours=19)
        session.now_ms = lambda: int(thursday.timestamp() * 1000)
        session.add_block(
            {
                "id": "school",
                "title": "School",
                "kind": "locked",
                "category": "class",
                "start": "08:00",
                "duration_min": 390,
                "days": [0, 1, 2, 3, 4],
            }
        )
        session.add_homework(
            {
                "id": "essay",
                "title": "History essay",
                "due": (date.fromisoformat(session.week_start) + timedelta(days=6)).isoformat(),
                "estimate_min": 60,
                "revision": 0,
            }
        )
        session.save()
        settled(qapp, made)
        work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
        work.update({"start": "18:45", "days": [NOW_DAY], "duration_min": 60})
        session.add_block(work)
        session.save()
        settled(qapp, made)
        yield made
    finally:
        with contextlib.suppress(RuntimeError):
            made.session.client.reset()
        made.hide()
        qapp.processEvents()
        server.stop()
        look_file().unlink(missing_ok=True)


def _homework(window: NativeWindow, key: str, title: str, minutes: int, due: str) -> None:
    window.session.add_homework(
        {"id": key, "title": title, "due": due, "estimate_min": minutes, "revision": 0}
    )
    window.session.save()
    settled(QApplication.instance(), window)


def _clean(window: NativeWindow, qapp: QApplication) -> None:
    """Every homework but the essay, and every block but School and the essay, gone."""
    session = window.session
    for key in [item for item in list(session.assignments) if item != "essay"]:
        assert session.delete_homework(key)
        settled(qapp, window)
    extras = [
        block["id"]
        for block in session.blocks
        if block["id"] != "school" and block.get("assignment_id") != "essay"
    ]
    for block_id in extras:
        session.delete_block(block_id)
    essay = session.assignments["essay"]
    if essay.get("completed"):
        session.complete_homework("essay", False)
    if extras or session.dirty:
        session.save()
    settled(qapp, window)


def _week_monday(window: NativeWindow) -> date:
    return date.fromisoformat(window.session.week_start)


def _centre(root: QObject, item: QObject) -> QPoint:
    spot = item.mapToScene(item.boundingRect().center())
    return QPoint(int(spot.x()), int(spot.y()))


def _click(window: NativeWindow, item: QObject, dx: int = 0, dy: int = 0) -> None:
    """A real left click on a QML item through the Quick widget, as the pointer does it."""
    quick = window._material_page._quick
    point = _centre(window._material_page.root, item) + QPoint(dx, dy)
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point)
    _pump(QApplication.instance())


def _drag(window: NativeWindow, item: QObject, to: QPoint) -> None:
    quick = window._material_page._quick
    start = _centre(window._material_page.root, item)
    app = QApplication.instance()
    QTest.mousePress(quick, Qt.MouseButton.LeftButton, pos=start)
    _pump(app, 4)
    steps = 12
    for step in range(1, steps + 1):
        spot = QPoint(
            start.x() + (to.x() - start.x()) * step // steps,
            start.y() + (to.y() - start.y()) * step // steps,
        )
        QTest.mouseMove(quick, spot)
        _pump(app, 2)
    QTest.mouseRelease(quick, Qt.MouseButton.LeftButton, pos=to)
    _pump(app, 6)


def _block_named(root: QObject, title: str) -> QObject:
    for block in _named(root, "weekBlock"):
        if any(str(label.property("text")) == title for label in _named(block, "title")):
            return block
    raise AssertionError(f"no block named {title}")


def _bridge(window: NativeWindow) -> QObject:
    return window._material_page.bridge


def _snack(window: NativeWindow) -> str:
    return str(_bridge(window).property("snackText"))


def _reset(window: NativeWindow, qapp: QApplication) -> QObject:
    """Material on screen on the account's week: standard density, weekends on, clock 24-hour."""
    set_clock_24h(True)
    if window.session.preferences and "dim_completed" in window.session.preferences:
        window.session.preferences.pop("dim_completed", None)
    _pref(window, show_weekends=True, clock_24h=True)
    session = window.session
    if session.week_start != window.home_week:
        session.load_week(window.home_week)
        settled(qapp, window)
    _clean(window, qapp)
    look_file().unlink(missing_ok=True)
    root = _show_material(qapp, window)
    if hasattr(window._material_page.bridge, "sheets"):
        window._material_page.bridge.sheets.forceClose()
    window._material_page.publish()
    _pump(qapp)
    return root


def test_plan_places_the_queue_and_undo_puts_it_back(qapp: QApplication, window: NativeWindow) -> None:
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

    # The button is a text button when disabled (no fill) and a click does nothing.
    plan = _qml(root, "planHomework")
    assert plan.property("enabled") is False
    assert plan.property("kind") == "text"
    shape = _named(plan, "shape")[0]
    wait_until(qapp, lambda: shape.property("color").alphaF() == 0.0)
    fill = shape.property("color")
    assert fill.alphaF() == 0.0
    # Its words stay readable: the muted ink at full opacity (B3a3, FIX-SPEC PR 6), not the 38 % disabled ink.
    label = _named(plan, "label")[0].property("color")
    assert label.name() == str(_bridge(window).property("theme")["inkMuted"]).lower()
    assert label.alphaF() == 1.0
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


def test_the_top_bar_undo_also_restores_a_plan(qapp: QApplication, window: NativeWindow) -> None:
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


def test_a_same_day_spread_says_so_in_the_snackbar(qapp: QApplication, window: NativeWindow) -> None:
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


def test_plan_is_disabled_when_nothing_needs_a_time(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    assert _qml(root, "homeworkCount").property("text") == "0"
    assert _qml(root, "planHomework").property("enabled") is False
    assert _qml(root, "homeworkEmptyText").property("text") == "Everything has a time."
    assert _qml(root, "homeworkHeading").property("text") == "No time yet · drag onto a day"


def test_status_tags_say_how_much_room_the_homework_has(qapp: QApplication, window: NativeWindow) -> None:
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
    assert details == sorted(
        [
            f"Due Thu {(monday + timedelta(days=NOW_DAY)).day} "
            f"{(monday + timedelta(days=NOW_DAY)).strftime('%b')}, 21:00 · 1 h",
            f"Due Thu {(monday + timedelta(days=NOW_DAY)).day} "
            f"{(monday + timedelta(days=NOW_DAY)).strftime('%b')}, 22:00 · 30 min",
            f"Due Sun {sunday.day} {sunday.strftime('%b')} · 30 min",
        ]
    )


def test_dragging_a_card_onto_the_grid_gives_it_that_hour(qapp: QApplication, window: NativeWindow) -> None:
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
    # 16:00 on Friday: the 17th hour row, a few pixels inside it.
    grid.setProperty("contentY", float(16 * row - 100))
    _pump(qapp)
    inside = hours_item.mapToScene(QPointF(gutter + friday * day_width + day_width / 2, 16 * row + 10))
    _drag(window, card, QPoint(int(inside.x()), int(inside.y())))
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    placed = next(block for block in window.session.blocks if block.get("assignment_id") == "sheet")
    assert placed["start"] == "16:00"
    assert placed["days"] == [friday]
    _pump(qapp)
    assert _qml(root, "homeworkCount").property("text") == "0"
    block = _block_named(root, "Math worksheet")
    assert int(block.property("y")) == 16 * row
    # The active Material snackbar is the only presenter; the Widgets toast stays hidden.
    assert "Math worksheet" in _snack(window)
    assert window.toast.isHidden()
    assert _qml(root, "materialSnackbar").property("actionText") == "UNDO"


def test_a_drop_off_the_grid_changes_nothing(qapp: QApplication, window: NativeWindow) -> None:
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


def test_clicking_homework_finishes_it_and_undo_opens_it_again(
    qapp: QApplication, window: NativeWindow
) -> None:
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


def test_a_fixed_block_is_not_a_button(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    school = _block_named(root, "School")
    assert school.property("homework") is False
    assert school.property("activeFocusOnTab") is False
    _click(window, school)
    _pump(qapp)
    assert _snack(window) == ""


def test_past_blocks_are_dimmed_by_the_clock(qapp: QApplication, window: NativeWindow) -> None:
    """Thursday 19:00: School is over Monday to Thursday, Friday is ahead, the essay is under way."""
    root = _reset(window, qapp)
    schools = [block for block in _named(root, "weekBlock") if block.property("title") == "School"]
    dayw = float(_qml(root, "materialWeek").property("dayWidth"))
    by_day = {int((float(block.property("x")) - 68) // dayw): block for block in schools}
    assert sorted(by_day) == [0, 1, 2, 3, 4]
    for day in (0, 1, 2, 3):
        assert by_day[day].property("past") is True
        assert abs(by_day[day].childItems()[0].property("opacity") - 1.0) < 0.001
        assert abs(_named(by_day[day], "shape")[0].property("opacity") - 0.55) < 0.001
        assert abs(_named(by_day[day], "bar")[0].property("opacity") - 0.55) < 0.001
        assert abs(_named(by_day[day], "title")[0].property("opacity") - 1.0) < 0.001
    assert by_day[4].property("past") is False
    assert abs(by_day[4].childItems()[0].property("opacity") - 1.0) < 0.001
    assert abs(_named(by_day[4], "shape")[0].property("opacity") - 1.0) < 0.001
    assert abs(_named(by_day[4], "bar")[0].property("opacity") - 1.0) < 0.001
    essay = _block_named(root, "History essay")
    assert essay.property("past") is False

    try:
        _pref(window, dim_completed=False)
        window._material_page.publish()
        _pump(qapp)
        for block in _named(root, "weekBlock"):
            assert block.property("past") is False
    finally:
        if window.session.preferences:
            window.session.preferences.pop("dim_completed", None)
        window._material_page.publish()


def test_a_week_that_is_over_is_all_past_and_one_ahead_is_not(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    session = window.session
    home = _week_monday(window)
    try:
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
    finally:
        session.load_week(window.home_week)
        settled(qapp, window)
        window._material_page.publish()


def test_weekends_off_gives_five_columns_forty_percent_wider(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    session = window.session
    saturday = {
        "id": "sat",
        "title": "Match",
        "kind": "locked",
        "category": "extra",
        "start": "10:00",
        "duration_min": 60,
        "days": [5],
    }
    session.add_block(saturday)
    session.save()
    settled(qapp, window)
    window._material_page.publish()
    _pump(qapp)
    week = _qml(root, "materialWeek")
    wide = float(week.property("dayWidth"))
    assert len(_named(root, "dayHeader")) == 7
    assert "Match" in _repeater_texts(root, "weekBlocks", "title")
    width = float(week.property("gridWidth")) - int(week.property("gutter"))
    assert abs(wide - width / 7) < 0.5

    _pref(window, show_weekends=False)
    window._material_page.publish()
    _pump(qapp)
    narrow = float(week.property("dayWidth"))
    assert len(_named(root, "dayHeader")) == 5
    names = [str(label.property("text")) for label in _named(root, "dayHeader")]
    assert not any(name.startswith(("Sat", "Sun")) for name in names)
    assert abs(narrow - width / 5) < 0.5
    assert abs(narrow / wide - 1.4) < 0.01
    assert "Match" not in _repeater_texts(root, "weekBlocks", "title")

    _pref(window, show_weekends=True)
    window._material_page.publish()
    _pump(qapp)
    assert len(_named(root, "dayHeader")) == 7
    assert "Match" in _repeater_texts(root, "weekBlocks", "title")


def test_a_missing_weekend_preference_reads_as_seven_columns(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    prefs = dict(window.session.preferences or {})
    prefs.pop("show_weekends", None)
    window.session.preferences = prefs
    window._material_page.publish()
    _pump(qapp)
    assert len(_named(root, "dayHeader")) == 7


def test_compact_density_shortens_the_hour_rows_to_44(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    assert int(essay.property("y")) == int(18.75 * 56)
    labels = _named(root, "hourLabel")
    assert int(labels[3].property("y")) == 3 * 56 - 8

    _look(window, density="compact")
    root = _show_material(qapp, window)
    assert int(_bridge(window).property("hourRow")) == 44
    essay = _block_named(root, "History essay")
    assert int(essay.property("y")) == int(18.75 * 44)
    school = _block_named(root, "School")
    assert int(school.property("y")) == 8 * 44
    assert int(school.property("height")) == int(6.5 * 44) - 2
    look_file().unlink(missing_ok=True)
    window._material_page.publish()


def test_hour_labels_follow_the_accounts_clock(qapp: QApplication, window: NativeWindow) -> None:
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


def test_the_day_headers_mark_today_and_carry_the_dates(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    monday = _week_monday(window)
    texts = _repeater_texts(root, "dayHeaders", "dayHeader")
    assert texts == [
        f"{name} {(monday + timedelta(days=index)).day}"
        for index, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
    ]
    headers = _named(root, "dayHeader")
    assert [bool(header.property("today")) for header in headers] == [index == NOW_DAY for index in range(7)]
    circles = _named(root, "dayDate")
    primary = _bridge(window).property("theme")["primary"].lower()
    filled = [circle for circle in circles if circle.property("color").alphaF() > 0]
    assert len(filled) == 1
    assert filled[0].property("color").name().lower() == primary


def test_the_top_bar_moves_the_week_and_today_comes_back(qapp: QApplication, window: NativeWindow) -> None:
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


def test_a_card_can_be_given_a_time_from_the_keyboard(qapp: QApplication, window: NativeWindow) -> None:
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


def test_blocks_that_just_landed_are_marked_fresh_once(qapp: QApplication, window: NativeWindow) -> None:
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


def test_clicking_toggle_weekends_swaps_between_seven_and_five_columns(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    toggle = _qml(root, "toggleWeekends")
    assert len(_named(root, "dayHeader")) == 7
    _click(window, toggle)
    settled(qapp, window)
    _pump(qapp)
    assert len(_named(root, "dayHeader")) == 5
    _click(window, toggle)
    settled(qapp, window)
    _pump(qapp)
    assert len(_named(root, "dayHeader")) == 7


def test_the_weekend_choice_survives_a_preferences_refresh_and_a_failed_save_restores_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    session = window.session
    _click(window, _qml(root, "toggleWeekends"))
    settled(qapp, window)
    assert session.preferences["show_weekends"] is False
    session._fetch_preferences()
    settled(qapp, window)
    _pump(qapp)
    assert session.preferences["show_weekends"] is False
    assert len(_named(root, "dayHeader")) == 5

    original = session.save_preferences

    def refuse(_updates: dict, then) -> bool:
        then(False)
        return True

    session.save_preferences = refuse
    try:
        _click(window, _qml(root, "toggleWeekends"))
        _pump(qapp)
        assert session.preferences["show_weekends"] is False
        assert len(_named(root, "dayHeader")) == 5
        assert _snack(window) == "Couldn't save the weekend setting. Try again."
        snackbar = _qml(root, "materialSnackbar")
        assert snackbar.property("actionText") == ""
        assert snackbar.property("activeFocusOnTab") is False
        undo_calls = []
        undo = session.undo
        session.undo = lambda: undo_calls.append(True)
        try:
            snackbar.actionClicked.emit()
            _pump(qapp)
            assert undo_calls == [], "A failed preference save cannot undo a schedule change"
        finally:
            session.undo = undo
    finally:
        session.save_preferences = original
        session.save_preferences({"show_weekends": True})
        settled(qapp, window)
        _bridge(window).note("")


def test_a_failed_week_load_is_not_retried_and_an_account_change_cancels_a_pending_one(
    qapp: QApplication, window: NativeWindow
) -> None:
    _reset(window, qapp)
    session = window.session
    home = session.week_start
    target = (date.fromisoformat(home) + timedelta(days=7)).isoformat()
    original = session.load_week
    calls = []

    def fail(start=None, **_kwargs) -> None:
        calls.append(start)
        session.busy = True
        session.busy_changed.emit(True)

    session.load_week = fail
    try:
        week = _bridge(window).property("week")
        week.next()
        session.busy = False
        session.busy_changed.emit(False)
        session.week_changed.emit()
        _pump(qapp, 12)
        assert calls == [target]
        assert session.week_start == home

        def pending(start=None, **_kwargs) -> None:
            calls.append(start)
            session.busy = True
            session.busy_changed.emit(True)

        session.load_week = pending
        week.next()
        week.next()
        session.busy = False
        session.busy_changed.emit(False)
        session.week_changed.emit()
        _pump(qapp, 12)
        later = (date.fromisoformat(home) + timedelta(days=14)).isoformat()
        assert calls == [target, target, later]

        week.next()
        session.account_changed.emit(None)
        session.busy = False
        session.busy_changed.emit(False)
        _pump(qapp, 12)
        assert calls == [target, target, later]
    finally:
        session.load_week = original


def test_tabbing_through_homework_cards_keeps_the_focused_card_visible(
    qapp: QApplication, window: NativeWindow
) -> None:
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


def test_the_drawn_week_keeps_block_words_and_bars_readable(qapp: QApplication, window: NativeWindow) -> None:
    """B3a3 (FIX-SPEC PR 6) on the real Week, light and dark: each block's title reaches 4.5:1 on the fill
    as drawn, past blocks included, with no fade from any ancestor; a current block's bar reaches 3:1 on
    the ground beside it."""
    from desktop.native.tokens import contrast

    root = _reset(window, qapp)
    panel = _bridge(window)._settings_bridge
    quick = window._material_page._quick
    try:
        for mode in ("light", "dark"):
            panel.setMode(mode)
            QTest.qWait(600)
            _pump(qapp)
            image = quick.grabFramebuffer()
            theme = _bridge(window).property("theme")
            grounds = {str(theme["page"]).lower(), str(theme["card"]).lower()}
            checked = {"past": 0, "current": 0}
            for block in _named(root, "weekBlock"):
                corner = block.mapToScene(QPointF(block.width() - 8, block.height() - 4)).toPoint()
                top = block.mapToScene(QPointF(2, 6)).toPoint()
                if not image.rect().contains(corner) or top.y() < 130:
                    continue
                title = _named(block, "title")[0]
                item, seen = title, 1.0
                while item is not None:
                    seen *= float(item.property("opacity"))
                    item = item.parentItem()
                assert seen > 0.999, f"{mode}: {title.property('text')} words faded to {seen:.2f}"
                fill = image.pixelColor(corner).name()
                words = title.property("color").name()
                assert contrast(words, fill) >= 4.5, f"{mode}: {title.property('text')} {words} on {fill}"
                past = bool(block.property("past"))
                checked["past" if past else "current"] += 1
                if not past:
                    edge = image.pixelColor(top).name()
                    # The ground beside the block, past the 1 px column line: the page, or the card on today.
                    spots = [block.mapToScene(QPointF(-step, 6)).toPoint() for step in range(2, 9)]
                    around = [image.pixelColor(spot).name() for spot in spots]
                    beside = next((colour for colour in around if colour in grounds), None)
                    assert beside is not None, f"{mode}: no page or card colour beside the block: {around}"
                    assert contrast(edge, beside) >= 3.0, f"{mode}: bar {edge} beside {beside}"
            assert checked["past"] >= 1 and checked["current"] >= 1, checked
    finally:
        look_file().unlink(missing_ok=True)
        _bridge(window).reload_material()
        panel.note_applied()
        _pump(qapp)

