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
    """The student shaped the homework by hand: its session pinned Thursday 19:30 (after the 19:00 clock),
    `minutes` long, saved."""
    session = window.session
    block = next(item for item in session.blocks if item.get("assignment_id") == assignment_id)
    block.update(duration_min=minutes, pinned=True, start="19:30", days=[3])
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

    assert _snack(window) == (
        "Placed 0 of 1 homework sessions. Science fair poster still has 9 h 55 min with no time."
    )
    assert session.message == "No homework was placed. Science fair poster still has 9 h 55 min with no time."
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
    assert (kept["duration_min"], kept["start"]) == (5, "19:30")


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

    assert _snack(window) == (
        "Placed 1 of 2 homework sessions. Science fair poster still has 9 h 55 min with no time."
    )
    assert window.session.message == (
        "Placed 1 homework session. Science fair poster still has 9 h 55 min with no time."
    )


@pytest.mark.parametrize(
    ("minutes", "said", "line"),
    [
        # 60 - 20 = 40: Plan places 30; 10 have no session.
        (
            20,
            "Placed 2 of 2 homework sessions. History essay still has 10 min with no time.",
            "History essay · 10 min with no time",
        ),
        # 60 - 15 = 45: Plan places all 45. Nothing is missing.
        (15, "Placed 2 of 2 homework sessions", ""),
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
    assert _snack(window) == "Placed 1 of 1 homework sessions. History essay still has 10 min with no time."


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


def _long_homework_on_thursday(window, qapp, start: str = "19:30") -> dict:
    """60 minutes of homework due 13 days out, its one 60 minute session pinned Thursday `start` of this
    week (by default after the 19:00 clock), saved, with the server's number (planned 60) read."""
    session = window.session
    due = (_week_monday(window) + timedelta(days=13)).isoformat()
    _homework(window, "long", "Long homework", 60, due)
    block = next(item for item in session.blocks if item.get("assignment_id") == "long")
    block.update(duration_min=60, pinned=True, start=start, days=[3])
    session._touch()
    session.save()
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["long"].get("planned_min") == 60)
    _pump(qapp)
    return block


def _long_counts(window) -> tuple[list[int], int, int, bool]:
    """The long homework's sessions in this week, its minutes no session holds, its time still needed, and
    whether the drawer's line names it."""
    session = window.session
    needed = {item["assignment_id"]: item["minutes"] for item in session.homework_time_needed()}
    lengths = [b["duration_min"] for b in session.blocks if b.get("assignment_id") == "long"]
    return (
        lengths,
        session.minutes_left_for("long"),
        needed.get("long", 0),
        "Long homework" in str(_bridge(window).week.property("leftoverWords")),
    )


def _move_long_next_week(window, qapp, reads: str) -> None:
    """Move the session from Thursday to Tuesday of next week while the server's re-read ("fail": never
    comes, "held": has not come yet, "land": comes at once)."""
    session = window.session
    block = next(item for item in session.blocks if item.get("assignment_id") == "long")
    monday = _week_monday(window)
    if reads != "land":
        _hold_the_assignments_reply(window, pytest.MonkeyPatch(), fail=reads == "fail")
    assert session.move_to_date(
        block["id"], (monday + timedelta(days=3)).isoformat(), (monday + timedelta(days=8)).isoformat()
    )
    settled(qapp, window)
    if reads == "land":
        wait_until(
            qapp, lambda: not any(b.get("assignment_id") == "long" for b in session._assignments_basis)
        )
        _pump(qapp)


@pytest.mark.parametrize("reads", ["fail", "held", "land"])
def test_a_session_moved_to_next_week_is_counted_there_at_once(qapp, window, reads: str) -> None:
    """60 minutes of homework, its one 60 minute session moved from this Thursday to next Tuesday. Next week
    holds the 60, so 60 - 60 = 0 minutes have no session and 0 are still needed, straight after the move,
    while the server's re-read has not come (or never comes), and after it lands. It said 60 until a read."""
    _reset(window, qapp)
    _long_homework_on_thursday(window, qapp)
    assert _long_counts(window) == ([60], 0, 0, False)
    _move_long_next_week(window, qapp, reads)

    assert _long_counts(window) == ([], 0, 0, False)
    assert _bridge(window).week.property("timeWords") != ""


@pytest.mark.parametrize("reads", ["fail", "held"])
def test_undoing_a_move_to_next_week_counts_the_week_it_comes_back_to(
    qapp, window, reads: str
) -> None:
    """Moved to next Tuesday (0 needed), then Undo: the session is back on this Thursday and next week holds
    nothing again, so 0 are needed, with the server's re-read not come."""
    _reset(window, qapp)
    _long_homework_on_thursday(window, qapp)
    _move_long_next_week(window, qapp, reads)
    window.session.undo()
    settled(qapp, window)

    assert _long_counts(window) == ([60], 0, 0, False)


@pytest.mark.parametrize("reads", ["fail", "held", "land"])
def test_a_session_moved_out_of_the_open_week_to_an_earlier_one_ahead_of_now_holds_its_time(
    qapp, window, reads: str
) -> None:
    """The session sits next Tuesday and next week is open (read: 60 held there, 0 needed). It is moved to
    this Friday, a week before the open one, keeping its 10:00. A session in any week holds its time while
    that time is ahead of now (Thursday 19:00), so Friday's holds the 60: 60 - 60 = 0 have no session and 0
    are needed, straight after the move, while the re-read has not come (or never comes), and after it
    lands. (The app refuses a move to a time that has passed, so the over case is the next-week test in
    test_planned_in_an_earlier_week_holds_its_time.py.)"""
    _reset(window, qapp)
    session = window.session
    _long_homework_on_thursday(window, qapp)
    _move_long_next_week(window, qapp, "land")
    monday = _week_monday(window)
    session.load_week((monday + timedelta(days=7)).isoformat())
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["long"].get("planned_min") == 60)
    _pump(qapp)
    block = next(item for item in session.blocks if item.get("assignment_id") == "long")
    if reads != "land":
        _hold_the_assignments_reply(window, pytest.MonkeyPatch(), fail=reads == "fail")
    moved = session.move_to_date(
        block["id"], (monday + timedelta(days=8)).isoformat(), (monday + timedelta(days=4)).isoformat()
    )
    assert moved, session.message
    settled(qapp, window)
    if reads == "land":
        wait_until(
            qapp, lambda: not any(b.get("assignment_id") == "long" for b in session._assignments_basis)
        )
        _pump(qapp)

    assert _long_counts(window) == ([], 0, 0, False)


@pytest.mark.parametrize("reads", ["fail", "held", "land"])
def test_a_session_moved_from_an_earlier_week_into_the_open_week_is_counted_once(
    qapp, window, reads: str
) -> None:
    """The session is on this Thursday and next week is open (the server counts from next week on: 0 planned,
    60 needed). It is moved into next Tuesday, in the open week: the open week now holds the 60, so 0 are
    needed, straight after the move and after the re-read lands."""
    _reset(window, qapp)
    session = window.session
    block = _long_homework_on_thursday(window, qapp, "10:00")
    monday = _week_monday(window)
    session.load_week((monday + timedelta(days=7)).isoformat())
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["long"].get("planned_min") == 0)
    _pump(qapp)
    if reads != "land":
        _hold_the_assignments_reply(window, pytest.MonkeyPatch(), fail=reads == "fail")
    assert session.move_to_date(
        block["id"], (monday + timedelta(days=3)).isoformat(), (monday + timedelta(days=8)).isoformat()
    ), session.message
    settled(qapp, window)
    if reads == "land":
        wait_until(qapp, lambda: any(b.get("assignment_id") == "long" for b in session._assignments_basis))
        _pump(qapp)

    assert _long_counts(window) == ([60], 0, 0, False)


@pytest.mark.parametrize("reads", ["fail", "held", "land"])
def test_plan_moving_last_weeks_waiting_session_into_this_week_needs_nothing_more(
    qapp, window, reads: str
) -> None:
    """60 minutes of homework due this Saturday, its only session waiting for a time in last week: 60 are
    needed here (the server counts from this week on). Plan moves it into this week and places it, so 0 are
    needed at once, with the re-read not come, and after it lands."""
    _reset(window, qapp)
    session = window.session
    home = session.week_start
    monday = _week_monday(window)
    _homework(window, "left", "Left homework", 60, (monday + timedelta(days=5)).isoformat())
    session.blocks = [b for b in session.blocks if b.get("assignment_id") != "left"]
    session._touch()
    session.save()
    settled(qapp, window)
    session.load_week((monday - timedelta(days=7)).isoformat())
    settled(qapp, window)
    session.add_block(
        {"id": "left-old", "title": "Left homework", "kind": "flexible", "category": "assignments",
         "duration_min": 60, "days": [4], "assignment_id": "left", "priority": 2, "energy": "medium"}
    )
    session.save()
    settled(qapp, window)
    session.load_week(home)
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["left"].get("planned_min") == 0)
    _pump(qapp)
    needed = lambda: {i["assignment_id"]: i["minutes"] for i in session.homework_time_needed()}.get("left", 0)  # noqa: E731
    assert needed() == 60
    if reads != "land":
        _hold_the_assignments_reply(window, pytest.MonkeyPatch(), fail=reads == "fail")
    session.solve()
    settled(qapp, window)
    if reads == "land":
        wait_until(qapp, lambda: any(b.get("assignment_id") == "left" for b in session._assignments_basis))
        _pump(qapp)

    here = [b for b in session.blocks if b.get("assignment_id") == "left"]
    assert [b["duration_min"] for b in here] == [60] and here[0].get("start"), (here, session.message)
    assert needed() == 0


@pytest.mark.parametrize("reads", ["fail", "held", "land"])
def test_undoing_a_delete_does_not_count_a_session_in_another_week_twice(
    qapp, window, reads: str
) -> None:
    """120 minutes of homework due in 13 days with 30 this Friday and 30 next Monday, read: 60 needed.
    Deleted (the read lands), then Undo with the re-read not come, or landing: its numbers come back as they
    were read, 120 - 30 - 30 = 60 needed. It said 30 until a read."""
    _reset(window, qapp)
    session = window.session
    home = session.week_start
    due = (_week_monday(window) + timedelta(days=13)).isoformat()
    _homework(window, "long", "Long homework", 120, due)
    block = next(b for b in session.blocks if b.get("assignment_id") == "long")
    block.update(duration_min=30, pinned=True, start="10:00", days=[4])
    session._touch()
    session.save()
    settled(qapp, window)
    later = deepcopy(block)
    later.update(id="later", days=[0])
    session.load_week((_week_monday(window) + timedelta(days=7)).isoformat())
    settled(qapp, window)
    session.add_block(later)
    session.save()
    settled(qapp, window)
    session.load_week(home)
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["long"].get("planned_min") == 60)
    _pump(qapp)
    needed = lambda: {i["assignment_id"]: i["minutes"] for i in session.homework_time_needed()}.get("long", 0)  # noqa: E731
    assert needed() == 60
    assert session.delete_homework("long")
    settled(qapp, window)
    wait_until(
        qapp,
        lambda: "long" not in session.assignments
        and not any(b.get("assignment_id") == "long" for b in session._assignments_basis),
    )
    _pump(qapp)
    if reads != "land":
        _hold_the_assignments_reply(window, pytest.MonkeyPatch(), fail=reads == "fail")
    session.undo()
    settled(qapp, window)
    if reads == "land":
        wait_until(qapp, lambda: session.assignments.get("long", {}).get("planned_min") == 60, timeout=10)
        _pump(qapp)

    assert needed() == 60


def test_plan_is_on_for_a_waiting_card_that_is_not_homework(qapp, window) -> None:
    """Only a 60 minute Study task with no time (no homework) is waiting: the drawer lists it and Plan
    places it, so the button is on."""
    root = _reset(window, qapp)
    session = window.session
    essay = next(b for b in session.blocks if b.get("assignment_id") == "essay")
    essay.update(duration_min=60, pinned=True, start="20:00", days=[4])
    session.add_block(
        {"id": "study1", "title": "Revise chemistry", "kind": "flexible", "category": "study",
         "duration_min": 60, "days": [4, 5, 6], "priority": 2, "energy": "medium"}
    )
    session._touch()
    session.save()
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["essay"].get("unplanned_min") == 0)
    _pump(qapp)

    assert _bridge(window).week.property("homeworkCount") == 1
    assert _qml(root, "planHomework").property("enabled") is True


@pytest.mark.parametrize("reads", ["fail", "held"])
def test_undoing_a_delete_after_a_cut_whose_read_has_not_landed_keeps_the_minutes(
    qapp, window, reads: str
) -> None:
    """Essay 60 with its 60 minute session, read. The session is cut to 5 and saved, and the server's re-read
    has not come: 60 - 5 = 55 have no session. The essay is deleted and the delete undone before a read comes:
    the essay is back with its 5 minute session, so 55 have no session and 55 are needed. It said 0."""
    _reset(window, qapp)
    session = window.session
    _cut_and_read(window, qapp, 60)
    _hold_the_assignments_reply(window, pytest.MonkeyPatch(), fail=reads == "fail")
    _cut(window, qapp, "essay", 5)
    assert _essay_counts(window) == ([5], 55, 55)
    assert session.delete_homework("essay")
    settled(qapp, window)
    session.undo()
    settled(qapp, window)

    assert _essay_counts(window) == ([5], 55, 55)


def test_plan_is_on_when_minutes_no_session_holds_are_enough_to_place(qapp, window) -> None:
    """Essay 60, session cut to 5, saved: 55 minutes have no session and 45 of them are whole quarter hours
    Plan can place, so the Plan button is on although no card is listed."""
    root = _reset(window, qapp)
    _cut(window, qapp, "essay", 5)
    wait_until(qapp, lambda: window.session.assignments["essay"].get("unplanned_min") == 55)
    _pump(qapp)

    assert _bridge(window).week.property("homeworkCount") == 0
    assert _qml(root, "planHomework").property("enabled") is True


def test_pressing_plan_with_only_minutes_no_session_holds_places_them(qapp, window) -> None:
    """Essay 60, session cut to 5 and pinned, saved: 55 minutes have no session, no card is listed and the
    button is on. Pressing it must place a new essay session: 45 of the 55 are whole quarter hours, so
    the essay then holds a second session of 45 minutes (it did nothing)."""
    root = _reset(window, qapp)
    session = window.session
    _cut(window, qapp, "essay", 5)
    wait_until(qapp, lambda: session.assignments["essay"].get("unplanned_min") == 55)
    _pump(qapp)
    assert _qml(root, "planHomework").property("enabled") is True

    _bridge(window).week.plan()
    wait_until(
        qapp,
        lambda: sorted(
            b["duration_min"] for b in session.blocks if b.get("assignment_id") == "essay"
        )
        == [5, 45]
        and not session.busy,
        what=lambda: repr(_snack(window)) + repr(session.message),
    )


def test_plan_is_off_when_nothing_is_left_to_place(qapp, window) -> None:
    """Essay 60 with its 60 minute session saved and read: every minute has a time."""
    root = _reset(window, qapp)
    _cut(window, qapp, "essay", 60)
    wait_until(qapp, lambda: window.session.assignments["essay"].get("unplanned_min") == 0)
    _pump(qapp)

    assert _qml(root, "planHomework").property("enabled") is False


@pytest.mark.parametrize(("pinned", "on"), [(False, True), (True, True)])
def test_plan_is_on_for_a_session_of_this_week_that_passed_pinned_or_not(
    qapp, window, pinned: bool, on: bool
) -> None:
    """Essay 60 with its 60 minute session on Monday 10:00, over by now (Thursday evening). Plan moves a
    session the planner placed; a session the student pinned stays, but its minutes still need a time,
    so the button is on for both."""
    root = _reset(window, qapp)
    session = window.session
    block = next(item for item in session.blocks if item.get("assignment_id") == "essay")
    block.update(duration_min=60, pinned=pinned, start="10:00", days=[0])
    session._touch()
    session.save()
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["essay"].get("planned_min") == 60)
    _pump(qapp)

    assert _qml(root, "planHomework").property("enabled") is on
