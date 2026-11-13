"""Material's Plan notice and homework drawer when some of a homework's minutes cannot be placed: the
notice's "Placed N of M" counts homework Plan tried, the drawer lists only minutes no session holds, and
nothing wrong shows between a save and the reply that brings the server's new number.
Expected values are worked out by hand in each docstring."""

# ruff: noqa: F811
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

import pytest

pytest.importorskip("PySide6")

from desktop.native.client import ApiError
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import (
    _bridge,
    _homework,
    _pump,
    _qml,
    _reset,
    _snack,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401


def _cut(window, qapp, assignment_id: str, minutes: int) -> None:
    """The student shaped the homework by hand: its session pinned Thursday 18:45, `minutes` long, saved."""
    session = window.session
    block = next(item for item in session.blocks if item.get("assignment_id") == assignment_id)
    block.update(duration_min=minutes, pinned=True, start="18:45", days=[3])
    session._touch()
    session.save()
    settled(qapp, window)


def _plan(window, qapp, root) -> None:
    """Plan my homework. Called on the session, because the button is off when only minutes with no
    session are left (no card to place); whether it should turn on is the owner's question."""
    window.session.solve()
    wait_until(
        qapp,
        lambda: (
            (_snack(window).startswith("Placed") or _snack(window).startswith("Nothing"))
            and not window.session.busy
        ),
        what=lambda: repr(_snack(window)) + repr(window.session.message),
    )
    settled(qapp, window)
    _pump(qapp)


def _poster(window, qapp) -> None:
    """600 minutes due Monday 08:00, its one session cut to 5. 600 - 5 = 595 still to do: Plan makes a
    585 minute session (whole quarter hours: 585 = 39 x 15) that finds no room before Monday, and 10 minutes
    are in no session at all."""
    due = f"{_week_monday(window).isoformat()}T08:00"
    _homework(window, "poster", "Science fair poster", 600, due)
    _cut(window, qapp, "poster", 5)
    wait_until(qapp, lambda: window.session.assignments["poster"].get("unplanned_min") == 595)
    _pump(qapp)


def test_a_plan_that_could_place_nothing_says_how_many_it_tried(qapp, window) -> None:
    """Poster alone: 0 placed, 1 homework with a session still waiting, so "Placed 0 of 1" (it said 0 of 0).
    The notice names the poster's 585 + 10 = 595 minutes = 9 h 55 min; the drawer's card holds the 585 and
    its line only the 10 that no session holds, so card and line add up to what the notice says."""
    root = _reset(window, qapp)
    session = window.session
    _poster(window, qapp)
    _plan(window, qapp, root)

    assert _snack(window) == "Placed 0 of 1. Science fair poster still has 9 h 55 min with no time."
    assert session.message == "Nothing placed. Science fair poster still has 9 h 55 min with no time."
    waiting = [b for b in session.blocks if b.get("assignment_id") == "poster" and not b.get("start")]
    assert [b["duration_min"] for b in waiting] == [585]
    assert _qml(root, "homeworkCount").property("text") == "1"
    line = _qml(root, "homeworkLeftover")
    assert line.property("visible") is True
    assert line.property("text") == "Science fair poster · 10 min with no time"
    assert [(i["title"], i["minutes"]) for i in session.homework_time_needed()] == [
        ("Science fair poster", 595)
    ]
    assert session.minutes_left_for("poster") == 10
    kept = next(b for b in session.blocks if b.get("pinned"))
    assert (kept["duration_min"], kept["start"]) == (5, "18:45")


def test_a_second_homework_that_was_placed_does_not_contradict_the_sentence(qapp, window) -> None:
    """Poster (a session waiting) and a 30 minute worksheet that Plan places: 1 placed of the 2 homework Plan
    tried. It said "Placed 1 of 1" in front of the poster still having 9 h 55 min with no time."""
    root = _reset(window, qapp)
    _poster(window, qapp)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    _pump(qapp)
    _plan(window, qapp, root)

    assert _snack(window) == "Placed 1 of 2. Science fair poster still has 9 h 55 min with no time."
    assert window.session.message == (
        "Placed 1 homework block. Science fair poster still has 9 h 55 min with no time."
    )


@pytest.mark.parametrize(
    ("minutes", "said", "line"),
    [
        # 60 - 20 = 40: Plan places 30; 10 have no session.
        (
            20,
            "Placed 2 of 2. History essay still has 10 min with no time.",
            "History essay · 10 min with no time",
        ),
        # 60 - 15 = 45: Plan places all 45. Nothing is missing.
        (15, "Placed 2 of 2", ""),
    ],
)
def test_the_drawer_line_lists_only_the_minutes_no_session_holds(
    qapp, window, minutes: int, said: str, line: str
) -> None:
    """The worksheet (30) is placed in both runs, hence two blocks of two."""
    root = _reset(window, qapp)
    _cut(window, qapp, "essay", minutes)
    wait_until(qapp, lambda: window.session.assignments["essay"].get("unplanned_min") == 60 - minutes)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "sheet", "Math worksheet", 30, due)
    settled(qapp, window)
    _pump(qapp)
    _plan(window, qapp, root)

    assert _snack(window) == said
    assert _bridge(window).week.property("leftoverWords") == line


def test_ten_minutes_too_short_for_plan_are_listed_and_plan_stays_off(qapp, window) -> None:
    """Essay 60, session cut to 50, saved: 10 minutes have no session and are under a quarter hour, so there
    is nothing for Plan to place. The drawer says so and the Plan button stays off."""
    root = _reset(window, qapp)
    _cut(window, qapp, "essay", 50)
    wait_until(qapp, lambda: window.session.assignments["essay"].get("unplanned_min") == 10)
    _pump(qapp)

    assert _qml(root, "planHomework").property("enabled") is False
    assert _qml(root, "homeworkEmptyText").property("text") == "History essay · 10 min with no time"


def _hold_the_assignments_reply(window, monkeypatch, *, fail: bool):
    """Hold back the reply to the request that re-reads each homework's unplanned minutes (or make it fail),
    so a test can look at the app in the time between a save and that reply. Returns the held replies."""
    session = window.session
    real = session.client.request
    held: list = []

    def request(method, path, payload, on_success, on_error):
        if method == "GET" and path.startswith("/api/assignments"):
            if fail:
                on_error(ApiError(0, "down"))
            else:
                held.append((path, payload, on_success, on_error))
            return None
        return real(method, path, payload, on_success, on_error)

    monkeypatch.setattr(session.client, "request", request)
    return real, held


def _drawer_and_counts(window) -> tuple[str, list[tuple[str, int]], int]:
    session = window.session
    return (
        _bridge(window).week.property("leftoverWords"),
        [(item["title"], item["minutes"]) for item in session.homework_time_needed()],
        session.minutes_left_for("essay"),
    )


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize(
    ("minutes", "after"),
    [
        # 60 - 5 = 55: Plan places 45, leaving 10 in no session.
        (5, ("History essay · 10 min with no time", [("History essay", 10)], 10)),
        # 60 - 15 = 45: Plan places all 45, leaving none.
        (15, ("", [], 0)),
    ],
)
def test_nothing_wrong_shows_between_a_save_and_the_reply_that_follows_it(
    qapp, window, monkeypatch, minutes: int, after: tuple, fail: bool
) -> None:
    """After Plan's sessions are saved, the server's number for the essay is still the old one (60 - the cut)
    until its next reply. Counting the new saved sessions against that old number showed "45 min with no
    time" (step 15) or 55 (step 5) for a moment, and for good if the reply never came. Every value taken
    from the save to the reply, and the end state, must be the true one."""
    root = _reset(window, qapp)
    session = window.session
    _cut(window, qapp, "essay", minutes)
    wait_until(qapp, lambda: session.assignments["essay"].get("unplanned_min") == 60 - minutes)
    _pump(qapp)
    real, held = _hold_the_assignments_reply(window, monkeypatch, fail=fail)

    seen: list = []

    def record() -> None:
        entry = _drawer_and_counts(window)
        if not seen or seen[-1] != entry:
            seen.append(entry)

    bridge = _bridge(window).week
    bridge.homeworkChanged.connect(record)
    session.week_changed.connect(record)
    session.save_finished.connect(lambda *_: record())
    _plan(window, qapp, root)
    record()
    if not fail:
        assert held, "the save should have asked for the server's new numbers"
    assert session.assignments["essay"].get("unplanned_min") == 60 - minutes, "the old number is still held"
    assert not session.dirty
    assert seen
    assert all(entry == after for entry in seen), seen

    if not fail:
        path, payload, on_success, on_error = held[-1]
        real("GET", path, payload, on_success, on_error)
        wait_until(qapp, lambda: session.assignments["essay"].get("unplanned_min") != 60 - minutes)
        settled(qapp, window)
        record()
        assert all(entry == after for entry in seen), seen


def test_a_session_in_another_week_is_still_counted_between_a_save_and_the_reply(
    qapp, window, monkeypatch
) -> None:
    """Homework of 60 minutes: 30 in this week (pinned Friday 10:00), 30 in next week. The server's number is
    60 - 60 = 0. The student shortens this week's session to 15 and it is saved; the server's number (still
    0) is not yet read again. 60 - 30 - 15 = 15 minutes have no session, before the reply and after it. The
    sessions of the other week are only in the server's number, so counting the new saved week against that
    number alone said 0 - 15 + 15 = 0."""
    _reset(window, qapp)
    session = window.session
    home = session.week_start
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "long", "Long homework", 60, due)
    block = next(item for item in session.blocks if item.get("assignment_id") == "long")
    block.update(duration_min=30, pinned=True, start="10:00", days=[4])
    session._touch()
    session.save()
    settled(qapp, window)
    later = deepcopy(block)
    later.update(id="later", days=[0], pinned=True)
    session.load_week((_week_monday(window) + timedelta(days=7)).isoformat())
    settled(qapp, window)
    session.add_block(later)
    session.save()
    settled(qapp, window)
    session.load_week(home)
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["long"].get("unplanned_min") == 0)
    _pump(qapp)
    assert session.minutes_left_for("long") == 0
    real, held = _hold_the_assignments_reply(window, monkeypatch, fail=False)

    block = next(item for item in session.blocks if item.get("assignment_id") == "long")
    block["duration_min"] = 15
    session._touch()
    session.save()
    settled(qapp, window)
    assert held, "the save should have asked for the server's new numbers"
    assert session.assignments["long"].get("unplanned_min") == 0, "the old number is still held"
    assert not session.dirty
    assert session.minutes_left_for("long") == 15
    assert _bridge(window).week.property("leftoverWords") == "Long homework · 15 min with no time"

    path, payload, on_success, on_error = held[-1]
    real("GET", path, payload, on_success, on_error)
    wait_until(qapp, lambda: session.assignments["long"].get("unplanned_min") == 15)
    settled(qapp, window)
    assert session.minutes_left_for("long") == 15
    assert _bridge(window).week.property("leftoverWords") == "Long homework · 15 min with no time"


def _long_across_weeks(window, qapp, here: int, there: int, estimate: int = 60) -> None:
    """`estimate` minutes of homework: `here` pinned Friday 10:00 this week, `there` next Monday, both saved,
    and the server's numbers read again."""
    session = window.session
    home = session.week_start
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "long", "Long homework", estimate, due)
    block = next(item for item in session.blocks if item.get("assignment_id") == "long")
    block.update(duration_min=here, pinned=True, start="10:00", days=[4])
    session._touch()
    session.save()
    settled(qapp, window)
    later = deepcopy(block)
    later.update(id="later", days=[0], pinned=True, duration_min=there)
    session.load_week((_week_monday(window) + timedelta(days=7)).isoformat())
    settled(qapp, window)
    session.add_block(later)
    session.save()
    settled(qapp, window)
    session.load_week(home)
    settled(qapp, window)
    expected = max(0, estimate - here - there)
    wait_until(qapp, lambda: session.assignments["long"].get("unplanned_min") == expected)
    _pump(qapp)


def test_an_unsaved_cut_to_homework_over_planned_across_weeks_shows_nothing_missing(qapp, window) -> None:
    """60 minutes of homework, 45 this week and 45 next week: 90 held, the server's number floored at 0. The
    student shortens this week's session to 30 and has not saved: 30 + 45 = 75 still held, more than 60, so
    nothing is missing and Plan has nothing to add. Counting the floored number said 15."""
    _reset(window, qapp)
    session = window.session
    _long_across_weeks(window, qapp, 45, 45)
    block = next(item for item in session.blocks if item.get("assignment_id") == "long")
    block["duration_min"] = 30
    session._touch()
    _pump(qapp)
    assert session.minutes_left_for("long") == 0
    needed = [(item["title"], item["minutes"]) for item in session.homework_time_needed()]
    assert ("Long homework", 15) not in needed
    assert _bridge(window).week.property("leftoverWords") == ""


@pytest.mark.parametrize("fail", [False, True])
def test_saving_a_change_to_homework_with_sessions_in_other_weeks_shows_nothing_missing(
    qapp, window, monkeypatch, fail: bool
) -> None:
    """60 minutes of homework, 30 this week and 30 next week: nothing missing. The student adds a note and
    it is saved. The save's answer carries the homework without the server's numbers; counting without them
    left out next week's 30 and said "30 min with no time" until the next read, or for good if it failed."""
    _reset(window, qapp)
    session = window.session
    _long_across_weeks(window, qapp, 30, 30)
    real, held = _hold_the_assignments_reply(window, monkeypatch, fail=fail)
    session.assignments["long"]["notes"] = "bring the atlas"
    session.dirty_assignments.add("long")
    session._touch()
    session.save()
    settled(qapp, window)
    _pump(qapp)
    assert not session.dirty
    assert session.minutes_left_for("long") == 0
    assert _bridge(window).week.property("leftoverWords") == ""
    if not fail:
        path, payload, on_success, on_error = held[-1]
        real("GET", path, payload, on_success, on_error)
        settled(qapp, window)
        _pump(qapp)
        assert session.minutes_left_for("long") == 0
        assert _bridge(window).week.property("leftoverWords") == ""


@pytest.mark.parametrize("fail", [False, True])
def test_undoing_a_longer_estimate_on_homework_with_sessions_in_other_weeks(
    qapp, window, monkeypatch, fail: bool
) -> None:
    """60 minutes of homework, 30 this week and 30 next week. The student raises it to 90 and saves: 90 - 60
    = 30 have no session. Undo puts 60 back: nothing is missing, before the server is read again and if that
    read fails. Undo put back the homework with the numbers read at 90, which still said 30."""
    _reset(window, qapp)
    session = window.session
    _long_across_weeks(window, qapp, 30, 30)
    session.assignments["long"]["estimate_min"] = 90
    session.dirty_assignments.add("long")
    session._touch("changing Long homework")
    session.save()
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["long"].get("unplanned_min") == 30)
    _pump(qapp)
    assert session.minutes_left_for("long") == 30
    real, held = _hold_the_assignments_reply(window, monkeypatch, fail=fail)
    session.undo()
    settled(qapp, window)
    _pump(qapp)
    assert session.assignments["long"]["estimate_min"] == 60
    assert session.minutes_left_for("long") == 0
    assert _bridge(window).week.property("leftoverWords") == ""
    if not fail:
        path, payload, on_success, on_error = held[-1]
        real("GET", path, payload, on_success, on_error)
        settled(qapp, window)
        _pump(qapp)
        assert session.minutes_left_for("long") == 0


def test_plan_sizes_its_rest_by_the_week_the_held_number_was_read_with(
    qapp, window, monkeypatch
) -> None:
    """Essay 60, its session pinned whole (60) and saved; the server read it (unplanned 0). The student cuts
    it to 5 and the save goes through, but the reply with the new number is held back. Plan counts against
    the week that held number was read with ([60]): later weeks hold 60 - 60 = 0, 60 - 5 = 55 have no
    session, so it adds a 45 minute rest and places it, and 60 - 5 - 45 = 10 are left. Read alone, the held
    0 gave Plan nothing to place."""
    root = _reset(window, qapp)
    session = window.session
    _cut(window, qapp, "essay", 60)
    wait_until(qapp, lambda: session.assignments["essay"].get("unplanned_min") == 0)
    _pump(qapp)
    _hold_the_assignments_reply(window, monkeypatch, fail=False)
    block = next(item for item in session.blocks if item.get("assignment_id") == "essay")
    block["duration_min"] = 5
    session._touch()
    session.save()
    settled(qapp, window)
    assert session.assignments["essay"].get("unplanned_min") == 0, "the old number is still held"
    _plan(window, qapp, root)

    essay = [b for b in session.blocks if b.get("assignment_id") == "essay" and b.get("start")]
    placed = sorted(b["duration_min"] for b in essay)
    assert placed == [5, 45]
    assert _snack(window) == "Placed 1 of 1. History essay still has 10 min with no time."


def _fail_saves(window, monkeypatch, status: int) -> dict:
    """Make every save fail with `status` while `state["on"]` is true."""
    session = window.session
    real = session.client.request
    state = {"on": True}

    def request(method, path, payload, on_success, on_error):
        if method == "POST" and path.startswith("/api/changes") and state["on"]:
            on_error(ApiError(status, "down"))
            return None
        return real(method, path, payload, on_success, on_error)

    monkeypatch.setattr(session.client, "request", request)
    return state


def _essay_counts(window) -> tuple[list[int], int, int]:
    """The essay's session lengths, its minutes no session holds, and its time still needed."""
    session = window.session
    needed = {item["assignment_id"]: item["minutes"] for item in session.homework_time_needed()}
    lengths = [b["duration_min"] for b in session.blocks if b.get("assignment_id") == "essay"]
    return lengths, session.minutes_left_for("essay"), needed.get("essay", 0)


def _cut_and_read(window, qapp, minutes: int) -> None:
    """The essay's session cut to `minutes`, saved, and its numbers read again."""
    _cut(window, qapp, "essay", minutes)
    wait_until(qapp, lambda: window.session.assignments["essay"].get("planned_min") == minutes)
    _pump(qapp)


@pytest.mark.parametrize("status", [0, 500])
def test_a_failed_undo_counts_the_week_it_goes_back_to(
    qapp, window, monkeypatch, status: int
) -> None:
    """Essay 60, its session 60, then cut to 5, saved and read again (planned 5). Undo puts the 60 back but
    its save fails, so the week goes back to the saved 5: 60 - 5 = 55 have no session. The copy it went back
    to held the numbers read before the cut (planned 60), which against the newer saved week said
    60 - (60 - 5) - 5 = 0."""
    _reset(window, qapp)
    _cut_and_read(window, qapp, 60)
    _cut_and_read(window, qapp, 5)
    assert _essay_counts(window) == ([5], 55, 55)
    _fail_saves(window, monkeypatch, status)
    window.session.undo()
    settled(qapp, window)

    assert _essay_counts(window) == ([5], 55, 55)


def test_a_failed_redo_counts_the_week_it_goes_back_to(qapp, window, monkeypatch) -> None:
    """Essay 60: cut to 5 and saved, undone (the 60 back, saved), read again (planned 60): 0 have no session.
    Redo cuts to 5 again but its save fails, so the week goes back to the saved 60: still 0. The copy it went
    back to held the numbers read after the cut (planned 5): 60 - (5 - 60) - 60 = 55 invented."""
    _reset(window, qapp)
    _cut_and_read(window, qapp, 60)
    _cut_and_read(window, qapp, 5)
    session = window.session
    session.undo()
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["essay"].get("planned_min") == 60)
    _pump(qapp)
    assert _essay_counts(window) == ([60], 0, 0)
    _fail_saves(window, monkeypatch, 0)
    session.redo()
    settled(qapp, window)

    assert _essay_counts(window) == ([60], 0, 0)


def _delete_essay_with_forty(window, qapp) -> None:
    """Essay 60, its session cut to 40 and read again (20 have no session), then deleted, and the read after
    the delete landed: the essay is in neither the server's list nor the saved week."""
    _cut_and_read(window, qapp, 40)
    assert _essay_counts(window) == ([40], 20, 20)
    session = window.session
    assert session.delete_homework("essay")
    settled(qapp, window)
    wait_until(
        qapp,
        lambda: "essay" not in session.assignments
        and not any(b.get("assignment_id") == "essay" for b in session._assignments_basis),
    )
    _pump(qapp)


@pytest.mark.parametrize("fail", [False, True])
def test_undoing_a_homework_delete_keeps_its_minutes(qapp, window, monkeypatch, fail: bool) -> None:
    """Undo brings the essay and its 40 back, with the numbers read before the delete (planned 40); the read
    after the Undo is held back, or fails. 60 - 40 = 20 have no session, before that read and after it.
    Counted against the saved week of after the delete, which has no essay, it said 60 - 40 - 40 < 0, so 0."""
    _reset(window, qapp)
    _delete_essay_with_forty(window, qapp)
    real, held = _hold_the_assignments_reply(window, monkeypatch, fail=fail)
    window.session.undo()
    settled(qapp, window)

    assert _essay_counts(window) == ([40], 20, 20)
    if not fail:
        path, payload, on_success, on_error = held[-1]
        real("GET", path, payload, on_success, on_error)
        settled(qapp, window)
        assert _essay_counts(window) == ([40], 20, 20)


def test_undoing_a_homework_delete_that_cannot_be_saved_then_can(qapp, window, monkeypatch) -> None:
    """Undo of the essay's delete, its save failing: the essay stays deleted, as the server has it, and is
    counted nowhere. Undo again, saved this time, with the read after it held back: 60 - 40 = 20 have no
    session; after the read, still 20."""
    _reset(window, qapp)
    _delete_essay_with_forty(window, qapp)
    session = window.session
    state = _fail_saves(window, monkeypatch, 0)
    session.undo()
    settled(qapp, window)
    assert "essay" not in session.assignments
    assert _essay_counts(window) == ([], 0, 0)

    state["on"] = False
    real, held = _hold_the_assignments_reply(window, monkeypatch, fail=False)
    session.undo()
    settled(qapp, window)
    assert _essay_counts(window) == ([40], 20, 20)
    path, payload, on_success, on_error = held[-1]
    real("GET", path, payload, on_success, on_error)
    settled(qapp, window)
    assert _essay_counts(window) == ([40], 20, 20)
