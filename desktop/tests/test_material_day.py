"""The Material Day and My day screens: counts, the free-time card, finishing with Undo, date picking.

Expected strings come from the spec (Jonathan's words) and from the clock set in the fixture,
not from reading the code's output.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.material.bridge_day import DayBridge  # noqa: E402
from desktop.native.material.day_board import board_for, read_flag  # noqa: E402
from desktop.native.weekmodel import Occurrence, set_clock_24h  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.server import LocalServer  # noqa: E402
from desktop.tests.logic_support import past_setup  # noqa: E402
from desktop.tests.test_layouts_window import PASSWORD, look_file, settled, wait_until  # noqa: E402
from desktop.tests.test_material_window import _pump, _show_material, _visuals  # noqa: E402

TODAY = date(2026, 11, 5)


def _block(
    title: str,
    start: int,
    end: int,
    *,
    work: bool = False,
    done: bool = False,
    missed: bool = False,
    assignment: str | None = None,
    category: str = "class",
    pinned: bool = False,
    due: str | None = None,
    slack: str | None = None,
) -> Occurrence:
    return Occurrence(
        block_id=title.lower().replace(" ", "-"),
        title=title,
        category=category,
        day=3,
        start=start,
        end=end,
        work=work,
        done=done,
        missed=missed,
        assignment_id=assignment,
        due=due,
        slack=slack,
        pinned=pinned,
    )


def _board(items: list[Occurrence], minute: int, when: str = "today", nudges: bool = True):
    set_clock_24h(True)
    return board_for(items, minute=minute, when=when, nudges=nudges, dim=True, mode="light", on=TODAY)


SCHOOL = (8 * 60, 12 * 60)
ESSAY = (18 * 60 + 45, 19 * 60 + 45)
SOCCER = (16 * 60, 17 * 60 + 30)


def test_the_count_line_says_things_left_today() -> None:
    day = [_block("School", *SCHOOL), _block("Soccer", *SOCCER, category="exercise"), _block("Essay", *ESSAY)]
    assert _board(day, 15 * 60).left_line == "2 things left today"
    assert _board(day, 17 * 60 + 40).left_line == "1 thing left today"
    assert _board(day, 20 * 60).left_line == "Nothing left today"
    assert _board([], 9 * 60).left_line == "Nothing left today"


def test_lists_split_by_the_clock_and_by_finishing() -> None:
    essay = _block("Essay", *ESSAY, work=True, assignment="a1", due="2026-11-08T23:59")
    over = _block("Maths", 17 * 60, 18 * 60, work=True, done=True, assignment="a2")
    board = _board([_block("School", *SCHOOL), over, essay], 15 * 60)
    assert [row.title for row in board.up_next] == ["Essay"]
    assert [row.title for row in board.done] == ["School", "Maths"]
    assert board.ring_count == 1
    assert board.ring_share == pytest.approx(2 / 3)
    assert board.up_next[0].can_finish is True
    assert board.done[0].can_finish is False
    assert "Due" in board.up_next[0].subtitle
    assert board.up_next[0].subtitle.startswith("18:45–19:45")


def test_rows_wear_the_spec_category_colours() -> None:
    day = [
        _block("School", *SCHOOL),
        _block("Soccer", *SOCCER, category="exercise"),
        _block("Essay", *ESSAY, work=True, assignment="a1", category="assignments"),
    ]
    set_clock_24h(True)
    light = board_for(day, minute=9 * 60, when="future", nudges=True, dim=True, mode="light", on=TODAY)
    # B3a3 class colours (FIX-SPEC PR 6): School, Sports, Work; each fill a faint tint of its bar.
    assert [row.fill for row in light.up_next] == ["#e4ebf7", "#e2f1ea", "#f3ecde"]
    assert [row.bar for row in light.up_next] == ["#3d6fc4", "#2f9e6b", "#a87512"]
    dark = board_for(day, minute=9 * 60, when="future", nudges=True, dim=True, mode="dark", on=TODAY)
    assert [row.fill for row in dark.up_next] == ["#1e2c44", "#1a372f", "#382e1a"]
    assert [row.bar for row in dark.up_next] == ["#3d6fc4", "#2f9e6b", "#a87512"]


def test_pinned_shows_in_the_row_note() -> None:
    board = _board([_block("Soccer", *SOCCER, pinned=True)], 9 * 60)
    assert board.up_next[0].subtitle == "16:00–17:30 · Pinned"


def test_status_tags_use_the_slack_words() -> None:
    """The three slack labels the week model already uses, plus none."""
    tight = _block("Essay", *ESSAY, work=True, assignment="a1", slack="tight")
    plenty = _block("Poster", 20 * 60, 21 * 60, work=True, assignment="a2", slack="ok")
    cutting = _block("Quiz", 21 * 60, 22 * 60, work=True, assignment="a3", slack="danger")
    board = _board([tight, plenty, cutting], 9 * 60)
    assert [(row.tag, row.tag_kind) for row in board.up_next] == [
        ("Tight", "tight"),
        ("Plenty of time", "plenty"),
        ("Cutting it close", "cutting"),
    ]
    finished = _block("Essay", *ESSAY, work=True, assignment="a1", done=True, slack="tight")
    done = _board([finished], 9 * 60)
    assert done.done[0].tag == ""
    assert done.done[0].tag_kind == ""


def test_the_now_card_is_the_gap_to_the_next_block() -> None:
    day = [_block("School", *SCHOOL), _block("Soccer", *SOCCER)]
    board = _board(day, 15 * 60 + 40)
    assert board.show_now is True
    assert board.now_title == "Free time before Soccer"
    assert board.now_minutes == 20
    assert board.now_line == "20 min left"
    longer = _board(day, 13 * 60)
    assert longer.now_minutes == 180
    assert longer.now_line == "3 h left"


def test_no_now_card_inside_a_block_after_the_last_one_or_off_today() -> None:
    day = [_block("School", *SCHOOL), _block("Soccer", *SOCCER)]
    assert _board(day, 10 * 60).show_now is False
    assert _board(day, 18 * 60).show_now is False
    assert _board(day, 13 * 60, when="future").show_now is False
    assert _board(day, 13 * 60, when="past").show_now is False


def test_a_finished_homework_block_does_not_end_the_gap() -> None:
    done_early = _block("Maths", 14 * 60, 15 * 60, work=True, done=True, assignment="a2")
    day = [done_early, _block("Soccer", *SOCCER)]
    board = _board(day, 14 * 60 + 30)
    assert board.show_now is True
    assert board.now_minutes == 90


def test_nudges_off_hides_the_card() -> None:
    day = [_block("School", *SCHOOL), _block("Soccer", *SOCCER)]
    assert _board(day, 13 * 60, nudges=False).show_now is False


def test_the_nudge_preference_reads_defensively() -> None:
    assert read_flag(None, ("free_time_nudges", "nudges"), True) is True
    assert read_flag({}, ("free_time_nudges", "nudges"), True) is True
    assert read_flag({"free_time_nudges": False}, ("free_time_nudges", "nudges"), True) is False
    assert read_flag({"nudges": False}, ("free_time_nudges", "nudges"), True) is False
    assert read_flag({"free_time_nudges": "no"}, ("free_time_nudges", "nudges"), True) is True


def test_start_focus_picks_the_next_homework_block() -> None:
    essay = _block("Essay", *ESSAY, work=True, assignment="a1")
    board = _board([_block("Soccer", *SOCCER), essay], 9 * 60)
    assert board.focus_block_id == "essay"
    assert board.focus_day == 3


def test_start_focus_uses_the_material_hook_when_the_window_has_one(qapp: QApplication) -> None:
    heard: list[tuple] = []

    class Window:
        session = SimpleNamespace()

        def start_material_focus(self, block_id: str, day: int) -> None:
            heard.append(("hook", block_id, day))

        def _start_focus(self, block_id: str, day: object) -> None:
            heard.append(("widgets", block_id, day))

    parent = QObject()
    bridge = DayBridge(Window(), parent)  # type: ignore[arg-type]
    bridge._publish(_board([_block("Essay", *ESSAY, work=True, assignment="a1")], 9 * 60))
    bridge.startFocus()
    assert heard == [("hook", "essay", 3)]


def test_start_focus_falls_back_to_the_widgets_start(qapp: QApplication) -> None:
    heard: list[tuple] = []

    class Window:
        session = SimpleNamespace(start_focus=lambda *args: heard.append(("session", args)))

        def _start_focus(self, block_id: str, day: object) -> None:
            heard.append(("widgets", block_id, day))

    parent = QObject()
    bridge = DayBridge(Window(), parent)  # type: ignore[arg-type]
    bridge._publish(_board([_block("Essay", *ESSAY, work=True, assignment="a1")], 9 * 60))
    bridge.startFocus()
    assert heard == [("widgets", "essay", 3)]


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-material-day"])
    yield application


@pytest.fixture(scope="module")
def window(qapp: QApplication, tmp_path_factory: pytest.TempPathFactory) -> Iterator[NativeWindow]:
    """Thursday 17:00: School 08:00-14:30 is over, History essay waits at 18:45."""
    look_file().unlink(missing_ok=True)
    server = LocalServer(tmp_path_factory.mktemp("materialday") / "flexweek.db")
    server.start()
    made = NativeWindow(server.origin)
    made.show()
    made.resize(1280, 800)
    try:
        made.username.setText("material_day_student")
        made.password.setText(PASSWORD)
        made.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "recoveryPage")
        made.recovery_ack.setChecked(True)
        made.recovery_continue.click()
        past_setup(qapp, made)
        wait_until(qapp, lambda: made.session.preferences is not None)
        session = made.session
        thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=17)
        session.now_ms = lambda: int(thursday.timestamp() * 1000)
        session.selected_day = thursday.date().isoformat()
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
                "due": sunday_due(session.week_start),
                "estimate_min": 60,
                "revision": 0,
            }
        )
        session.save()
        settled(qapp, made)
        work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
        work.update({"start": "18:45", "days": [3], "duration_min": 60})
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


def _bridge(root: QObject) -> QObject:
    bridge = root.property("bridge")
    assert bridge is not None
    return bridge


def _rows(model: QObject) -> list[dict]:
    """Every row of a Rows model as a dict, read the way a QML delegate reads it."""
    names = {int(role): bytes(name).decode() for role, name in model.roleNames().items()}
    found = []
    for at in range(model.rowCount()):
        index = model.index(at, 0)
        found.append({name: model.data(index, role) for role, name in names.items()})
    return found


def test_day_screen_reads_the_real_day(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    prefs = dict(session.preferences or {})
    prefs["clock_24h"] = True
    prefs.pop("free_time_nudges", None)
    prefs.pop("nudges", None)
    session.preferences = prefs
    root = _show_material(qapp, window)
    day = _bridge(root).property("day")
    assert day.property("leftLine") == "1 thing left today"
    assert day.property("showNow") is True
    assert day.property("nowTitle") == "Free time before History essay"
    assert day.property("nowMinutes") == 105
    assert day.property("nowLine") == "1 h 45 min left"
    up = _rows(day.property("upNext"))
    done = _rows(day.property("doneRows"))
    assert [row["title"] for row in up] == ["History essay"]
    assert up[0]["subtitle"].startswith("18:45–19:45")
    assert up[0]["canFinish"] is True
    assert [row["title"] for row in done] == ["School"]
    assert done[0]["subtitle"] == "08:00–14:30"
    myday = _bridge(root).property("myday")
    assert myday.property("ringCount") == 1
    assert myday.property("ringCaption") == "thing left"
    assert myday.property("ringShare") == pytest.approx(0.5)
    window._use_widgets_styles()


def test_the_clock_setting_changes_the_row_times(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    prefs = dict(session.preferences or {})
    prefs["clock_24h"] = False
    session.preferences = prefs
    root = _show_material(qapp, window)
    day = _bridge(root).property("day")
    done = _rows(day.property("doneRows"))
    assert done[0]["subtitle"] == "8 AM–2:30 PM"
    prefs["clock_24h"] = True
    session.preferences = prefs
    window._use_widgets_styles()


def test_finishing_homework_moves_it_to_done_and_undo_brings_it_back(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _show_material(qapp, window)
    bridge = _bridge(root)
    day = bridge.property("day")
    assert day.property("leftLine") == "1 thing left today"
    day.finishHomework("essay")
    settled(qapp, window)
    _pump(qapp)
    assert day.property("leftLine") == "Nothing left today"
    assert [row["title"] for row in _rows(day.property("upNext"))] == []
    assert [row["title"] for row in _rows(day.property("doneRows"))] == ["School", "History essay"]
    assert day.property("showNow") is False
    assert bridge.property("snackText") == "Finished History essay"
    bridge.undo()
    settled(qapp, window)
    _pump(qapp)
    assert day.property("leftLine") == "1 thing left today"
    assert [row["title"] for row in _rows(day.property("upNext"))] == ["History essay"]
    assert bridge.property("snackText") == ""
    window._use_widgets_styles()


def test_nudges_off_hides_the_card_on_both_screens(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    prefs = dict(session.preferences or {})
    prefs["free_time_nudges"] = False
    session.preferences = prefs
    root = _show_material(qapp, window)
    bridge = _bridge(root)
    assert bridge.property("day").property("showNow") is False
    assert bridge.property("myday").property("showNow") is False
    prefs["free_time_nudges"] = True
    session.preferences = prefs
    root = _show_material(qapp, window)
    assert _bridge(root).property("day").property("showNow") is True
    assert _bridge(root).property("myday").property("showNow") is True
    window._use_widgets_styles()


def test_picking_a_date_shows_that_day_and_my_day_stays_on_today(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    root = _show_material(qapp, window)
    bridge = _bridge(root)
    day = bridge.property("day")
    thursday = date.fromisoformat(session.selected_day)
    friday = thursday + timedelta(days=1)
    assert day.property("miniDay") == thursday.day
    day.pickDay(friday.day)
    settled(qapp, window)
    _pump(qapp)
    assert session.selected_day == friday.isoformat()
    assert day.property("miniDay") == friday.day
    assert day.property("leftLine") == "1 thing left"
    assert [row["title"] for row in _rows(day.property("upNext"))] == ["School"]
    assert day.property("showNow") is False
    day.previousDay()
    settled(qapp, window)
    _pump(qapp)
    assert session.selected_day == thursday.isoformat()
    assert day.property("leftLine") == "1 thing left today"
    day.nextDay()
    settled(qapp, window)
    _pump(qapp)
    assert session.selected_day == friday.isoformat()
    myday = bridge.property("myday")
    assert myday.property("leftLine") == "1 thing left today"
    day.pickDay(thursday.day)
    settled(qapp, window)
    window._use_widgets_styles()


def test_the_day_screen_has_the_named_controls(qapp: QApplication, window: NativeWindow) -> None:
    root = _show_material(qapp, window)
    _bridge(root).showPage("day")
    _pump(qapp)
    names = {str(item.objectName()) for item in _visuals(root)}
    for name in (
        "materialDay",
        "dayPrevious",
        "dayNext",
        "dayLeftLine",
        "dayNow",
        "dayNowTitle",
        "dayStartFocus",
        "dayFinish",
        "dayMonthToggle",
        "dayMonthSide",
        "dayMiniMonth",
        "dayNowLabel",
        "dayUpNext",
        "dayDone",
    ):
        assert name in names, name
    _bridge(root).showPage("myday")
    _pump(qapp)
    names = {str(item.objectName()) for item in _visuals(root)}
    for name in ("materialMyDay", "myDayRing", "myDayNow", "myDayStartFocus", "myDayCount"):
        assert name in names, name
    window._use_widgets_styles()


def test_a_snackbar_line_clears_itself_but_not_a_newer_one(qapp: QApplication, window: NativeWindow) -> None:
    bridge = _bridge(_show_material(qapp, window))
    bridge.note("First line")
    bridge.note("Second line")
    bridge._clear_snack("First line")
    assert bridge.property("snackText") == "Second line"
    bridge._clear_snack("Second line")
    assert bridge.property("snackText") == ""
    window._use_widgets_styles()


def _hold_changes(session, monkeypatch: pytest.MonkeyPatch) -> tuple[list, object]:
    original = session.client.request
    held: list = []

    def delay(method, path, body, ok, fail):
        if method == "POST" and path == "/api/changes":
            held.append((method, path, body, ok, fail))
        else:
            original(method, path, body, ok, fail)

    monkeypatch.setattr(session.client, "request", delay)
    return held, original


def test_finishing_homework_waits_while_a_save_is_pending(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = window.session
    root = _show_material(qapp, window)
    day = _bridge(root).property("day")
    held, original = _hold_changes(session, monkeypatch)
    try:
        session.add_homework(
            {
                "id": "busy-check",
                "title": "Busy check",
                "due": sunday_due(session.week_start),
                "estimate_min": 30,
                "revision": 0,
            }
        )
        session.save()
        assert session.busy and held
        day.finishHomework("essay")
        assert session.assignments["essay"].get("completed") is not True
        assert _bridge(root).property("snackText") == (
            "Saving your last change… That check will work in a moment."
        )
    finally:
        monkeypatch.setattr(session.client, "request", original)
        while held:
            original(*held.pop(0))
        settled(qapp, window)
        if "busy-check" in session.assignments:
            session.delete_homework("busy-check")
            settled(qapp, window)
        window._use_widgets_styles()


def test_myday_keeps_today_after_browsing_another_week(qapp: QApplication, window: NativeWindow) -> None:
    root = _show_material(qapp, window)
    bridge = _bridge(root)
    session = window.session
    current = session.week_start
    next_week = (date.fromisoformat(current) + timedelta(days=7)).isoformat()
    past_week = (date.fromisoformat(current) + timedelta(days=-7)).isoformat()
    try:
        bridge.showPage("myday")
        settled(qapp, window)
        _pump(qapp)
        myday = bridge.property("myday")
        initial = myday.property("upNext").rowCount()
        assert initial > 0
        assert myday.property("waiting") is False
        bridge.showPage("week")
        session.load_week(next_week)
        settled(qapp, window)
        bridge.showPage("myday")
        settled(qapp, window)
        _pump(qapp)
        assert myday.property("waiting") is False
        assert myday.property("loadError") == ""
        assert myday.property("upNext").rowCount() == initial
        session.load_week(past_week)
        settled(qapp, window)
        settled(qapp, window)
        _pump(qapp)
        assert myday.property("upNext").rowCount() == initial
        future = (date.fromisoformat(current) + timedelta(days=21)).isoformat()
        session.open_day(future)
        settled(qapp, window)
        bridge.showPage("myday")
        settled(qapp, window)
        _pump(qapp)
        assert myday.property("upNext").rowCount() == initial
        bridge.showPage("month")
        settled(qapp, window)
        session.shift_month(1)
        settled(qapp, window)
        bridge.showPage("myday")
        settled(qapp, window)
        _pump(qapp)
        assert myday.property("upNext").rowCount() == initial
    finally:
        session.load_week(current)
        settled(qapp, window)
        window._use_widgets_styles()
