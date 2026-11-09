"""Material's Edit and Add homework refuse a pinned time that has already passed today, in the words the
app uses for a past time, and save nothing. The one clock reads Thursday 19:00 of the open week."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)

PAST = "That time has passed. Choose 7:00 PM or later today, or another day."


def essay_start(shell) -> str:
    block = next(b for b in shell.session.blocks if b.get("assignment_id") == "essay")
    return block["start"]


def test_a_pinned_time_already_past_today_is_refused_and_nothing_is_saved(qapp, shell, sheets) -> None:
    sheets.editHomework("essay")
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", 3)
    sheets.setText("whenTime", "18:30")
    sheets.save()
    settle(qapp, shell)
    assert sheets.kind == "homework", "the sheet stays open on the refusal"
    assert sheets.form["whenProblem"] == PAST
    assert essay_start(shell) == "18:45", "nothing was saved"


def test_a_pinned_time_still_ahead_today_saves(qapp, shell, sheets) -> None:
    sheets.editHomework("essay")
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", 3)
    sheets.setText("whenTime", "19:30")
    sheets.save()
    settle(qapp, shell)
    assert sheets.form.get("whenProblem", "") == ""
    assert essay_start(shell) == "19:30"


def test_the_field_says_the_time_has_passed_as_soon_as_it_is_picked(qapp, shell, sheets) -> None:
    sheets.editHomework("essay")
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", 3)
    sheets.setText("whenTime", "18:30")
    assert sheets.form["whenProblem"] == PAST
    sheets.setText("whenTime", "19:30")
    assert sheets.form["whenProblem"] == ""


def test_a_pinned_time_already_past_is_refused_for_homework_that_is_pinned_already(
    qapp, shell, sheets
) -> None:
    work = next(b for b in shell.session.blocks if b.get("assignment_id") == "essay")
    work.update({"start": "20:00", "days": [3], "pinned": True})
    shell.session.add_block(work)
    shell.session.save()
    settle(qapp, shell)
    sheets.editHomework("essay")
    assert sheets.form["whenProblem"] == "", "opening it changes nothing"
    sheets.setText("whenTime", "18:30")
    sheets.save()
    settle(qapp, shell)
    assert sheets.form["whenProblem"] == PAST
    assert essay_start(shell) == "20:00"


def test_a_pinned_time_that_was_already_past_when_opened_is_left_alone(qapp, shell, sheets) -> None:
    """The essay sits at 18:45 and the clock is 19:00: opening and saving it is not the student's mistake."""
    work = next(b for b in shell.session.blocks if b.get("assignment_id") == "essay")
    work.update({"pinned": True})
    shell.session.add_block(work)
    shell.session.save()
    settle(qapp, shell)
    sheets.editHomework("essay")
    assert sheets.form["whenProblem"] == ""
    sheets.save()
    settle(qapp, shell)
    assert sheets.kind != "homework", "the sheet closed: it saved without a refusal"


def test_finished_homework_is_not_told_its_pinned_time_has_passed(qapp, shell, sheets) -> None:
    sheets.editHomework("essay")
    sheets.setFlag("completed", True)
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", 3)
    sheets.setText("whenTime", "18:30")
    assert sheets.form["whenProblem"] == ""


def test_a_pinned_time_on_a_day_ahead_is_not_told_it_has_passed(qapp, shell, sheets) -> None:
    sheets.editHomework("essay")
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", 4)
    sheets.setText("whenTime", "18:30")
    assert sheets.form["whenProblem"] == ""


def test_switching_away_from_and_back_to_the_same_pinned_time_is_not_a_mistake(
    qapp, shell, sheets
) -> None:
    """The essay is pinned at 18:45, which is before the 19:00 clock; picking "Plan it for me" and then
    "At a set time" again leaves the time exactly as it was, so there is nothing to refuse."""
    work = next(b for b in shell.session.blocks if b.get("assignment_id") == "essay")
    work.update({"pinned": True})
    shell.session.add_block(work)
    shell.session.save()
    settle(qapp, shell)
    sheets.editHomework("essay")
    sheets.setText("when", "plan")
    sheets.setText("when", "fixed")
    assert sheets.form["whenProblem"] == ""


def test_ticking_finished_clears_the_message_about_a_time_that_has_passed(qapp, shell, sheets) -> None:
    sheets.editHomework("essay")
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", 3)
    sheets.setText("whenTime", "18:30")
    assert sheets.form["whenProblem"] == PAST
    sheets.setFlag("completed", True)
    assert sheets.form["whenProblem"] == ""
