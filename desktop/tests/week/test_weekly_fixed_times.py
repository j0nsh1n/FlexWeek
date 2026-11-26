"""A fixed time that repeats every week, from the Material block sheet: what the student sees in the open
week and in the weeks around it after adding one, changing it, ending it, deleting it and undoing it.

The clock is Thursday 5 Nov 2026, 19:00. Guitar is on Friday 17:00 for an hour; Friday is the 6th, the next
weeks' Fridays are the 13th, 20th and 27th. Expected values come from those dates, not from the sheet."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from desktop.native.calendar import date_for_day, day_short
from desktop.tests.material_support import pump
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.waiting import wait_until

FRIDAY = 4
SAVED = "Changed Guitar from this week on. Undo also takes back anything changed after it."


def _friday(session, weeks: int = 0) -> str:
    base = date.fromisoformat(date_for_day(session.week_start, FRIDAY))
    return (base + timedelta(days=7 * weeks)).isoformat()


def _go(qapp, shell, offset: int) -> None:
    """Show the week `offset` weeks from the one the test started in."""
    session = shell.session
    target = (date.fromisoformat(shell.opened_week) + timedelta(days=7 * offset)).isoformat()
    session.load_week(target)
    wait_until(qapp, lambda: session.week_start == target and not session.busy)
    pump(qapp, 10)


def _guitar(shell) -> list[dict]:
    return [b for b in shell.session.blocks if b["title"] == "Guitar"]


def _starts(shell) -> list[tuple[str, list[int]]]:
    return [(b["start"], sorted(b["days"])) for b in _guitar(shell)]


def _settled(qapp, shell) -> None:
    settle(qapp, shell)
    pump(qapp, 10)


@pytest.fixture()
def week(qapp, shell):
    shell.opened_week = shell.session.week_start
    return shell


def _fill(sheets, *, title="Guitar", days=(FRIDAY,), start="17:00", weekly=True, until=None) -> None:
    sheets.openBlock()
    sheets.setText("title", title)
    sheets.next()
    for day in [item["value"] for item in sheets.form["days"] if item["on"]]:
        sheets.toggleDay(day)
    for day in days:
        sheets.toggleDay(day)
    sheets.setText("start", start)
    if weekly:
        sheets.setFlag("repeat", True)
    if until:
        sheets.setText("until", until)


def _add_weekly(qapp, shell, sheets, **fields) -> dict:
    _fill(sheets, **fields)
    sheets.next()
    sheets.next()
    _settled(qapp, shell)
    return next(r for r in shell.session.repeats if r["title"] == fields.get("title", "Guitar"))


def _edit(sheets, repeat_id: str, day: int = -1) -> None:
    sheets.editBlock(repeat_id, day)


def test_a_weekly_time_with_until_shows_from_this_week_to_until_and_not_before_or_after(
    qapp, week, sheets
) -> None:
    until = _friday(week.session, 1)
    _add_weekly(qapp, week, sheets, until=until)
    assert _starts(week) == [("17:00", [FRIDAY])]
    assert sheets.notice == (
        "Guitar repeats every week from this week on. Undo also takes back anything changed after it."
    )
    _go(qapp, week, 1)
    assert _starts(week) == [("17:00", [FRIDAY])], "the week of Until still has it"
    _go(qapp, week, 2)
    assert _guitar(week) == [], "the week after Until does not"
    _go(qapp, week, -1)
    assert _guitar(week) == [], "the week before was never part of it"


def test_turning_the_switch_on_for_a_one_off_makes_it_one_copy_here_and_every_week_after(
    qapp, week, sheets
) -> None:
    week.session.add_block(
        {
            "id": "guitar-1",
            "title": "Guitar",
            "kind": "locked",
            "category": "extra",
            "start": "17:00",
            "duration_min": 60,
            "days": [FRIDAY],
        }
    )
    week.session.save()
    _settled(qapp, week)
    _go(qapp, week, 1)
    assert _guitar(week) == [], "a one-off stays in its own week"
    _go(qapp, week, 0)
    _edit(sheets, "guitar-1", FRIDAY)
    assert sheets.form["showRepeat"] is True and sheets.form["repeat"] is False
    sheets.setFlag("repeat", True)
    sheets.next()
    assert sheets.ask == {}, "turning the switch on asks nothing"
    _settled(qapp, week)
    assert _starts(week) == [("17:00", [FRIDAY])], "one copy in this week, not two"
    for offset in (1, 2):
        _go(qapp, week, offset)
        assert _starts(week) == [("17:00", [FRIDAY])]


def test_undo_names_turning_the_switch_on_as_changing_it(qapp, week, sheets) -> None:
    # Reviewer's nit: the one-off goes as part of the change, so the step is not "deleting Guitar".
    week.session.add_block({"id": "guitar-1", "title": "Guitar", "kind": "locked", "category": "extra",
                            "start": "17:00", "duration_min": 60, "days": [FRIDAY]})  # fmt: skip
    week.session.save()
    _settled(qapp, week)
    _edit(sheets, "guitar-1", FRIDAY)
    sheets.setFlag("repeat", True)
    sheets.next()
    _settled(qapp, week)
    week.session.undo()
    wait_until(qapp, lambda: str(week.session.message).startswith("Undid"))
    assert week.session.message == "Undid changing Guitar."


def _weekly_open(qapp, week, sheets, **fields):
    repeat = _add_weekly(qapp, week, sheets, **fields)
    _edit(sheets, repeat["id"])
    return repeat


def test_changing_the_start_for_this_week_and_later_changes_this_and_later_weeks_not_last_week(
    qapp, week, sheets
) -> None:
    _weekly_open(qapp, week, sheets)
    sheets.setText("start", "18:00")
    sheets.next()
    assert sheets.ask["id"] == "block-save"
    assert [card["title"] for card in sheets.ask["cards"]] == [
        "This week only",
        "This week and every week after",
    ]
    sheets.answer("later")
    _settled(qapp, week)
    assert _starts(week) == [("18:00", [FRIDAY])]
    _go(qapp, week, 1)
    assert _starts(week) == [("18:00", [FRIDAY])]
    _go(qapp, week, -1)
    assert _guitar(week) == [], "last week never had Guitar"


def test_changing_the_start_for_this_week_only_changes_only_this_week(qapp, week, sheets) -> None:
    _weekly_open(qapp, week, sheets)
    sheets.setText("start", "18:00")
    sheets.next()
    sheets.answer("week")
    _settled(qapp, week)
    assert _starts(week) == [("18:00", [FRIDAY])]
    _go(qapp, week, 1)
    assert _starts(week) == [("17:00", [FRIDAY])]


def test_a_later_change_is_built_from_the_repeat_not_from_this_weeks_own_copy(qapp, week, sheets) -> None:
    repeat = _add_weekly(qapp, week, sheets)
    _edit(sheets, repeat["id"])
    sheets.setText("start", "18:00")
    sheets.next()
    sheets.answer("week")
    _settled(qapp, week)
    _edit(sheets, repeat["id"])
    sheets.setText("category", "sport")
    sheets.next()
    sheets.answer("later")
    _settled(qapp, week)
    _go(qapp, week, 1)
    assert [(b["start"], b["category"]) for b in _guitar(week)] == [("17:00", "sport")], (
        "later weeks keep the repeat's 17:00; this week's hand-made 18:00 is not copied into them"
    )


def test_ticking_a_day_keeps_the_days_until_hid_from_this_week(qapp, week, sheets) -> None:
    # Guitar on Thursday and Friday ends Thursday 5 Nov, so this week shows Thursday only. Ticking Wednesday
    # and moving Until a week on must not drop Friday, which this week never showed (the old #118 failure).
    thursday = date_for_day(week.session.week_start, 3)
    repeat = _add_weekly(qapp, week, sheets, days=(3, FRIDAY), until=thursday)
    assert _starts(week) == [("17:00", [3])]
    _edit(sheets, repeat["id"])
    sheets.toggleDay(2)
    sheets.setText("until", _friday(week.session, 1))
    sheets.next()
    sheets.answer("later")
    _settled(qapp, week)
    _go(qapp, week, 1)
    assert _starts(week) == [("17:00", [2, 3, FRIDAY])]


def test_a_change_to_one_day_asks_nothing_and_leaves_the_other_days_and_weeks(qapp, week, sheets) -> None:
    repeat = _add_weekly(qapp, week, sheets, days=(FRIDAY, 5))
    _edit(sheets, repeat["id"], FRIDAY)
    assert sheets.form["scope"] == "occurrence"
    assert sheets.form["showRepeat"] is False, "a one-day sheet does not offer the repeat's switch or Until"
    sheets.setText("start", "18:00")
    sheets.next()
    assert sheets.ask == {}, "a one-day change is this week only, with no question"
    _settled(qapp, week)
    assert sorted(_starts(week)) == [("17:00", [5]), ("18:00", [FRIDAY])]
    _go(qapp, week, 1)
    assert _starts(week) == [("17:00", [FRIDAY, 5])]


def test_only_until_changed_asks_nothing_and_cuts_the_weeks_after_it(qapp, week, sheets) -> None:
    _weekly_open(qapp, week, sheets)
    sheets.setText("until", _friday(week.session, 1))
    sheets.next()
    assert sheets.ask == {}
    _settled(qapp, week)
    _go(qapp, week, 1)
    assert _starts(week) == [("17:00", [FRIDAY])]
    _go(qapp, week, 2)
    assert _guitar(week) == []


def test_moving_until_later_brings_the_days_back_and_clearing_it_ends_nothing(qapp, week, sheets) -> None:
    repeat = _add_weekly(qapp, week, sheets, until=_friday(week.session, 1))
    _go(qapp, week, 2)
    assert _guitar(week) == []
    _go(qapp, week, 0)
    _edit(sheets, repeat["id"])
    sheets.setText("until", _friday(week.session, 3))
    sheets.next()
    _settled(qapp, week)
    _go(qapp, week, 3)
    assert _starts(week) == [("17:00", [FRIDAY])]
    _go(qapp, week, 4)
    assert _guitar(week) == []
    _go(qapp, week, 0)
    _edit(sheets, repeat["id"])
    assert sheets.form["until"] == _friday(week.session, 3)
    sheets.setText("until", "")
    assert sheets.form["untilLabel"] == "No end"
    sheets.next()
    assert sheets.ask == {}
    _settled(qapp, week)
    _go(qapp, week, 6)
    assert _starts(week) == [("17:00", [FRIDAY])], "no end again"


def test_switch_off_keeps_this_week_as_a_one_off_and_ends_the_weeks_after(qapp, week, sheets) -> None:
    repeat = _weekly_open(qapp, week, sheets)
    assert sheets.form["repeat"] is True
    sheets.setFlag("repeat", False)
    sheets.next()
    assert sheets.ask == {}
    _settled(qapp, week)
    assert sheets.notice == (
        "Guitar stops repeating after this week. Undo also takes back anything changed after it."
    )
    assert _starts(week) == [("17:00", [FRIDAY])]
    assert [b["id"] for b in _guitar(week)] == [repeat["id"].removeprefix("weekly-")]
    _go(qapp, week, 1)
    assert _guitar(week) == []


def test_switch_off_with_removed_days_keeps_only_active_days_and_keeps_repeats_whole_on_error(
    qapp, week, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    repeat = _add_weekly(qapp, week, sheets, days=(0, 2, FRIDAY))
    current = next(b for b in week.session.blocks if b["id"] == repeat["id"])
    week.session.add_block({**current, "removed_days": [2, FRIDAY]})
    week.session.save()
    _settled(qapp, week)

    # A refused one-off must leave repeats untouched and keep the sheet open.
    def refuse(_block: dict) -> dict:
        raise ValueError("one-off refused")

    monkeypatch.setattr(week.session, "check_block", refuse)
    _edit(sheets, repeat["id"], 0)
    sheets.setFlag("repeat", False)
    sheets.next()
    assert sheets.kind == "block"
    assert sheets.form["error"] == "one-off refused"
    assert any(r["id"] == repeat["id"] for r in week.session.repeats)
    monkeypatch.undo()

    # With validation passing, the stopped one-off keeps only Monday and carries no removed_days.
    sheets.next()
    assert sheets.ask == {}
    _settled(qapp, week)
    assert _starts(week) == [("17:00", [0])]
    kept = _guitar(week)[0]
    assert kept["id"] == repeat["id"].removeprefix("weekly-")
    assert not kept.get("removed_days")
    _go(qapp, week, 1)
    assert _guitar(week) == []


def test_delete_this_week_only_keeps_later_weeks_and_this_week_and_later_takes_them_all(
    qapp, week, sheets
) -> None:
    repeat = _add_weekly(qapp, week, sheets)
    sheets.askDeleteBlock(repeat["id"], -1)
    assert [card["id"] for card in sheets.ask["cards"]] == ["week", "every"]
    assert sheets.ask["cards"][1]["line"].endswith("Undo also takes back anything changed after it.")
    sheets.answer("week")
    _settled(qapp, week)
    assert _guitar(week) and all(b.get("removed_days") == b["days"] for b in _guitar(week))
    _go(qapp, week, 1)
    assert _starts(week) == [("17:00", [FRIDAY])]
    sheets.askDeleteBlock(repeat["id"], -1)
    sheets.answer("every")
    _settled(qapp, week)
    assert _guitar(week) == []
    _go(qapp, week, 2)
    assert _guitar(week) == []


def test_undo_of_this_week_and_later_puts_the_earlier_state_back_and_says_it_takes_later_changes_too(
    qapp, week, sheets
) -> None:
    _weekly_open(qapp, week, sheets)
    sheets.setText("start", "18:00")
    sheets.next()
    sheets.answer("later")
    _settled(qapp, week)
    wait_until(qapp, lambda: sheets.noticeUndo)
    assert sheets.notice == SAVED
    sheets.undoNotice()
    wait_until(qapp, lambda: _starts(week) == [("17:00", [FRIDAY])])
    _go(qapp, week, 1)
    assert _starts(week) == [("17:00", [FRIDAY])]


def test_a_weekly_time_that_doubles_a_hand_made_copy_names_the_week_and_removes_nothing(
    qapp, week, sheets
) -> None:
    _go(qapp, week, 1)
    week.session.add_block(
        {
            "id": "hand",
            "title": "Guitar",
            "kind": "locked",
            "category": "extra",
            "start": "17:00",
            "duration_min": 60,
            "days": [FRIDAY],
        }
    )
    week.session.save()
    _settled(qapp, week)
    _go(qapp, week, 0)
    _fill(sheets)
    sheets.next()
    sheets.next()
    wait_until(qapp, lambda: sheets.ask.get("id") == "doubled-weeks")
    named_week = date.fromisoformat(week.opened_week) + timedelta(days=7)
    assert sheets.ask["title"] == "Guitar is already in a later week"
    assert sheets.ask["body"] == (
        f"Guitar also sits on its own in the week of {named_week.day} {named_week.strftime('%b')}, so it "
        "shows twice there. Delete the extra one in that week if you don't want both."
    )
    assert [a["id"] for a in sheets.ask["answers"]] == ["ok"]
    sheets.answer("ok")
    assert sheets.ask == {}
    _go(qapp, week, 1)
    assert len(_guitar(week)) == 2, "both show, nothing was removed"


def test_an_until_before_the_first_day_shows_the_sentence_and_does_not_save(qapp, week, sheets) -> None:
    session = week.session
    before = (date.fromisoformat(_friday(session)) - timedelta(days=1)).isoformat()
    _fill(sheets, until=before)
    expected = f"Until can't be before the first day, {day_short(_friday(session), date(2026, 11, 5))}."
    assert sheets.form["untilProblem"] == expected
    sheets.next()
    sheets.next()
    assert sheets.kind == "block", "the sheet stays open"
    assert sheets.form["untilProblem"] == expected
    assert session.repeats == [r for r in session.repeats if r["title"] != "Guitar"]
    assert _guitar(week) == []


def test_setup_run_again_leaves_a_weekly_time_alone(qapp, week, sheets) -> None:
    session = week.session
    _add_weekly(qapp, week, sheets)
    session.set_setup_blocks(
        [
            {
                "id": "school",
                "title": "School",
                "kind": "locked",
                "category": "class",
                "start": "08:00",
                "duration_min": 390,
                "days": [0, 1, 2, 3, 4],
            }
        ]
    )
    stops = [item for item in (session._repeat_send or []) if str(item.get("id")).startswith("weekly-")]
    assert stops == [], "nothing is sent for the weekly time"
    session.save()
    _settled(qapp, week)
    assert _starts(week) == [("17:00", [FRIDAY])]
    _go(qapp, week, 1)
    assert _starts(week) == [("17:00", [FRIDAY])]


def test_finishing_setups_week_page_again_leaves_a_weekly_time_alone(qapp, week, sheets) -> None:
    # Reviewer's case: the Setup page itself, not the session call, decides what stands after it.
    from desktop.native.setup_steps import WEEK

    _add_weekly(qapp, week, sheets)
    week._open_setup(WEEK, first_run=False)
    setup = week._material_page.bridge.account
    setup.setupNext()
    _settled(qapp, week)
    stops = [item for item in (week.session._repeat_send or []) if str(item.get("id")).startswith("weekly-")]
    assert stops == [], "nothing is sent for the weekly time"
    assert _starts(week) == [("17:00", [FRIDAY])]
    _go(qapp, week, 1)
    assert _starts(week) == [("17:00", [FRIDAY])]


def test_copying_last_weeks_fixed_times_leaves_out_a_weekly_time(qapp, week, sheets) -> None:
    # Reviewer's case: the weekly time is already in this week, so a copy would show it twice.
    _add_weekly(qapp, week, sheets)
    week.session.add_block({"id": "gym", "title": "Gym", "kind": "locked", "start": "19:00",
                            "duration_min": 60, "days": [FRIDAY]})  # fmt: skip
    week.session.save()
    _settled(qapp, week)
    _go(qapp, week, 1)
    got: list = []
    week.session.copy_last_week_fixed_rows(got.append)
    wait_until(qapp, lambda: bool(got))
    assert [row["block"]["title"] for row in (got[0] or [])] == ["Gym"]


def test_the_201st_repeat_is_refused_with_the_stores_sentence_and_the_sheet_stays(qapp, week, sheets) -> None:
    """A week holds at most 100 blocks, so 200 repeats cannot be written through the session: the store's
    refusal (its sentence, from engine repeats.rs REPEATS_FULL) is given to the save instead, and the sheet
    must show it and stay open."""
    from desktop.native.client import ApiError

    sentence = (
        "FlexWeek keeps at most 200 weekly blocks (School, activities and weekly fixed times) in one "
        "account. Delete one before adding another."
    )
    client = week.session.client
    real = client.request

    def refuse(method, path, body, ok, err, *args, **kwargs):
        if path == "/api/changes" and (body or {}).get("repeats"):
            err(ApiError(422, sentence))
            return None
        return real(method, path, body, ok, err, *args, **kwargs)

    client.request = refuse
    try:
        _fill(sheets)
        sheets.next()
        sheets.next()
        wait_until(qapp, lambda: sentence in str(sheets.form.get("error")))
        assert sheets.kind == "block", "the sheet stays open"
        _settled(qapp, week)
        assert _guitar(week) == [], "the refused weekly time is taken back off the week"
        assert week.session.pending_save is None, "nothing refused waits to be sent again"
    finally:
        client.request = real
    # Room again (another one stopped elsewhere): Save on the same sheet goes through.
    sheets.save()
    _settled(qapp, week)
    assert _starts(week) == [("17:00", [FRIDAY])]
