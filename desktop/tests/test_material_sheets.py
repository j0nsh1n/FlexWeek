"""Material sheets and the More menu, in the real shell.

Expected words and values come from the Widgets sheets' wording and from the week the fixture
builds (School Monday to Friday 08:00 to 14:30, a History essay Thursday 18:45, clock held at
Thursday 19:00), not from reading what the bridge returns.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QPushButton  # noqa: E402

from desktop.native.client import ApiError  # noqa: E402
from desktop.native.material.bridge_sheets import WAIT_DELETE, WAIT_SAVE  # noqa: E402
from desktop.native.widgets import PreviewDialog  # noqa: E402
from desktop.native.window import WINDOW_MIN_WIDTH, NativeWindow  # noqa: E402
from desktop.tests.logic_support import past_setup  # noqa: E402,F401
from desktop.tests.test_layouts_window import wait_until  # noqa: E402
from desktop.tests.test_material_window import (  # noqa: E402,F401
    _named,
    _pump,
    _qml,
    _show_material,
    _visuals,
)
from desktop.tests.test_material_window import qapp as base_qapp  # noqa: E402,F401
from desktop.tests.test_material_window import window as base_window  # noqa: E402,F401

DISCARD = "Discard what you typed?"
TITLE_PROBLEM = "Give the homework a title."
SHORT = "Give it at least 15 minutes."
MULTIPLE = "Use a multiple of 15 minutes, such as 15, 30, or 45."
LONG = "That's more than 24 hours. Split it into parts and add each part as its own homework."
DUE_PASSED = "That due time has passed. Choose a later one."


@pytest.fixture(scope="module")
def qapp(request: pytest.FixtureRequest) -> QApplication:
    return request.getfixturevalue("base_qapp")


@pytest.fixture(scope="module")
def shell(request: pytest.FixtureRequest) -> NativeWindow:
    return request.getfixturevalue("base_window")


def _find(root, name: str):
    found = _named(root, name)
    assert found, name
    return found[0]


@pytest.fixture()
def sheets(qapp: QApplication, shell: NativeWindow):
    root = _show_material(qapp, shell)
    bridge = shell._material_page.bridge.sheets
    session = shell.session
    kept_homework = set(session.assignments)
    kept_blocks = {item["id"] for item in session.blocks}
    yield bridge
    bridge.forceClose()
    _settle(qapp, shell)
    for assignment_id in set(session.assignments) - kept_homework:
        session.delete_homework(assignment_id)
    for item in list(session.blocks):
        if item["id"] not in kept_blocks and not item.get("assignment_id"):
            session.delete_block(item["id"], scope="series", day=None, every_week=False)
    if session.dirty:
        session.save()
    _settle(qapp, shell)
    bridge.closeMore()
    bridge.dismissNotice()
    shell.resize(1280, 800)
    _pump(qapp)
    assert root is not None
    shell._use_widgets_styles()


def _settle(qapp: QApplication, shell: NativeWindow) -> None:
    wait_until(qapp, lambda: not shell.session.busy and not shell.session.dirty)


def _type_homework(sheets, title: str) -> None:
    sheets.setText("title", title)


def test_add_homework_goes_what_when_how_long_then_saves_through_the_session(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    shell._material_page.bridge.addHomework()
    form = sheets.form
    assert sheets.kind == "homework"
    assert form["heading"] == "Add homework"
    assert [crumb["label"] for crumb in form["crumbs"]] == ["1. What", "2. When", "3. How long"]
    assert form["prompt"] == "What is it?"
    assert form["primary"] == "Next"
    assert form["canDelete"] is False

    sheets.next()
    assert sheets.form["titleProblem"] == TITLE_PROBLEM
    assert sheets.form["step"] == 0

    _type_homework(sheets, "Chemistry lab")
    assert sheets.form["titleProblem"] == ""
    sheets.next()
    assert sheets.form["step"] == 1
    assert sheets.form["prompt"] == "When is it due?"
    # Tomorrow from Thursday, at the end of the day.
    friday = (datetime.fromisoformat(shell.session.week_start) + timedelta(days=4)).date().isoformat()
    assert sheets.form["dueDate"] == friday
    assert sheets.form["canBack"] is True
    sheets.back()
    assert sheets.form["step"] == 0
    sheets.next()
    sheets.next()
    assert sheets.form["step"] == 2
    assert sheets.form["prompt"] == "How long will it take?"
    assert sheets.form["primary"] == "Save"
    assert sheets.form["estimate"] == "60"
    assert sheets.form["estimateSuffix"] == "min"
    assert [item["label"] for item in sheets.form["quickLengths"]] == [
        "15 min",
        "30 min",
        "45 min",
        "60 min",
        "90 min",
    ]

    sheets.setText("estimate", "45")
    sheets.next()
    assert sheets.kind == ""
    found = [item for item in shell.session.assignments.values() if item["title"] == "Chemistry lab"]
    assert len(found) == 1
    assert found[0]["estimate_min"] == 45
    assert found[0]["due"].startswith(friday)
    assert sheets.notice == "Added Chemistry lab"
    assert sheets.noticeUndo is True
    _settle(qapp, shell)


def test_homework_estimate_and_due_are_checked_with_the_widgets_words(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openHomework()
    _type_homework(sheets, "Reading")
    sheets.next()
    sheets.next()
    for typed, said in (("10", SHORT), ("50", MULTIPLE), ("1500", LONG)):
        sheets.setText("estimate", typed)
        sheets.next()
        assert sheets.kind == "homework", typed
        assert sheets.form["estimateProblem"] == said
    sheets.setText("estimate", "30")
    # Monday has already gone by on Thursday evening.
    monday = shell.session.week_start
    sheets.setText("dueDate", monday)
    sheets.next()
    assert sheets.kind == "homework"
    assert sheets.form["step"] == 1
    assert sheets.form["dueProblem"] == DUE_PASSED
    assert not [item for item in shell.session.assignments.values() if item["title"] == "Reading"]


def test_homework_title_over_80_characters_is_refused_with_the_widgets_words(sheets) -> None:
    sheets.openHomework()
    _type_homework(sheets, "x" * 81)
    sheets.next()
    sheets.next()
    sheets.next()
    assert sheets.kind == "homework"
    assert sheets.form["titleProblem"] == "Keep the homework title under 80 characters."
    assert sheets.form["step"] == 0


def test_the_discard_prompt_keeps_typed_work_until_the_student_says_discard(sheets) -> None:
    sheets.openHomework()
    sheets.closeSheet()
    assert sheets.kind == ""

    sheets.openHomework()
    _type_homework(sheets, "Essay")
    sheets.closeSheet()
    assert sheets.kind == "homework"
    assert sheets.ask["title"] == DISCARD
    assert sheets.ask["body"] == "Your changes will be lost."
    assert [item["label"] for item in sheets.ask["answers"]] == ["Keep editing", "Discard"]
    sheets.answer("keep")
    assert sheets.kind == "homework"
    assert sheets.ask == {}
    assert sheets.form["title"] == "Essay"
    sheets.closeSheet()
    sheets.answer("discard")
    assert sheets.kind == ""


def test_edit_homework_changes_the_title_and_delete_asks_first(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.editHomework("essay")
    form = sheets.form
    assert form["heading"] == "Edit homework"
    assert form["title"] == "History essay"
    assert form["canDelete"] is True
    assert form["step"] == -1
    assert form["primary"] == "Save"
    assert form["placedLine"].startswith("Planned Thu")

    sheets.setText("title", "History essay, draft 2")
    sheets.save()
    assert shell.session.assignments["essay"]["title"] == "History essay, draft 2"
    _settle(qapp, shell)

    sheets.editHomework("essay")
    sheets.remove()
    assert sheets.ask["title"] == "Delete homework"
    assert "Its times on the calendar go too, in every week." in sheets.ask["body"]
    sheets.answer("stay")
    assert "essay" in shell.session.assignments
    sheets.remove()
    sheets.answer("delete")
    wait_until(qapp, lambda: "essay" not in shell.session.assignments)
    assert sheets.kind == ""
    assert sheets.notice == "Deleted History essay, draft 2."
    _settle(qapp, shell)
    shell.session.undo()
    _settle(qapp, shell)
    assert "essay" in shell.session.assignments
    # Put the fixture's title back for the tests after this one.
    sheets.editHomework("essay")
    sheets.setText("title", "History essay")
    sheets.save()
    _settle(qapp, shell)
    assert shell.session.assignments["essay"]["title"] == "History essay"


def test_more_details_carry_course_type_energy_notes_links_and_steps(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openHomework()
    _type_homework(sheets, "Lab report")
    sheets.next()
    sheets.next()
    assert sheets.form["detailsOpen"] is False
    sheets.setFlag("detailsOpen", True)
    sheets.setText("course", "Chemistry")
    sheets.setNumber("priority", 1)
    sheets.setText("energy", "high")
    sheets.setText("notes", "Bring goggles")
    sheets.addLink()
    assert sheets.form["detailsError"] == "A link needs a label and an http(s) address."
    sheets.setText("linkLabel", "Rubric")
    sheets.setText("linkUrl", "https://example.org/rubric")
    sheets.addLink()
    assert sheets.form["links"] == [{"label": "Rubric", "url": "https://example.org/rubric"}]
    assert sheets.form["linkLabel"] == ""
    sheets.addCheck()
    assert sheets.form["detailsError"] == "A checklist step needs text."
    sheets.setText("checkText", "Write the aim")
    sheets.addCheck()
    sheets.toggleCheck(0)
    sheets.next()
    saved = next(item for item in shell.session.assignments.values() if item["title"] == "Lab report")
    assert saved["course"] == "Chemistry"
    assert saved["priority"] == 1
    assert saved["energy"] == "high"
    assert saved["notes"] == "Bring goggles"
    assert saved["links"] == [{"label": "Rubric", "url": "https://example.org/rubric"}]
    assert [(step["text"], step["done"]) for step in saved["checklist"]] == [("Write the aim", True)]
    assert "spotify_url" not in sheets.form
    _settle(qapp, shell)


def test_spread_over_days_shows_its_line_and_saves_sessions(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openHomework()
    _type_homework(sheets, "Project")
    sheets.next()
    sunday = (datetime.fromisoformat(shell.session.week_start) + timedelta(days=6)).date().isoformat()
    sheets.setText("dueDate", sunday)
    sheets.next()
    sheets.setText("estimate", "120")
    assert sheets.form["spreadShown"] is True
    sheets.setText("spread", "spread")
    assert sheets.form["spreadLine"].startswith("2 × 60 min")
    sheets.next()
    assert sheets.kind == ""
    _settle(qapp, shell)
    made = next(item for item in shell.session.assignments.values() if item["title"] == "Project")

    def sessions() -> list[dict]:
        return [b for b in shell.session.blocks if b.get("assignment_id") == made["id"]]

    wait_until(qapp, lambda: len(sessions()) == 2)
    assert sorted(b["duration_min"] for b in sessions()) == [60, 60]
    _settle(qapp, shell)


def test_add_fixed_time_steps_and_saves_through_the_session(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openBlock()
    form = sheets.form
    assert form["heading"] == "Add fixed time"
    assert [crumb["label"] for crumb in form["crumbs"]] == ["1. What", "2. When", "3. Category"]
    sheets.next()
    assert sheets.form["titleProblem"] == "Give it a title."
    sheets.setText("title", "Chess club")
    sheets.next()
    assert sheets.form["step"] == 1
    sheets.setText("start", "17:00")
    # End follows Start by the length it had: an hour.
    assert sheets.form["end"] == 18 * 60
    assert sheets.form["durationLine"].startswith("End moved to")
    for day in [item["value"] for item in sheets.form["days"] if item["on"]]:
        sheets.toggleDay(day)
    sheets.next()
    assert sheets.form["daysProblem"] == "Tick at least one day."
    sheets.toggleDay(5)
    sheets.next()
    assert sheets.form["step"] == 2
    assert sheets.form["primary"] == "Add"
    sheets.setText("category", "extra")
    sheets.next()
    assert sheets.kind == ""
    made = next(item for item in shell.session.blocks if item["title"] == "Chess club")
    assert made["days"] == [5]
    assert made["start"] == "17:00"
    assert made["duration_min"] == 60
    assert made["category"] == "extra"
    _settle(qapp, shell)


def test_fixed_time_checks_end_after_start_and_previews_a_clash(sheets) -> None:
    sheets.openBlock()
    sheets.setText("title", "Study hall")
    sheets.next()
    for day in [item["value"] for item in sheets.form["days"] if item["on"]]:
        sheets.toggleDay(day)
    sheets.toggleDay(0)
    sheets.setText("start", "09:00")
    # School is Monday 08:00 to 14:30. Material draws the two overlapped, one a little over the other
    # (Jonathan, 2026-11-08), so the sheet says that, not "side by side".
    assert sheets.form["clash"] == "School is at that time too. Both will show, one slightly over the other."
    sheets.setNumber("end", 9 * 60)
    assert sheets.form["durationIsProblem"] is True
    assert sheets.form["durationLine"].startswith("End needs to be later than Start")
    assert sheets.form["clash"] == ""
    sheets.next()
    assert sheets.form["step"] == 1
    assert sheets.form["timeProblem"].startswith("End needs to be later than Start")


def test_edit_a_fixed_time_in_a_series_and_delete_it(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    shell.session.add_block(
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "category": "extra",
            "start": "16:00",
            "duration_min": 60,
            "days": [4, 5],
        }
    )
    shell.session.save()
    _settle(qapp, shell)
    sheets.editBlock("club", 4)
    form = sheets.form
    assert form["heading"] == "Edit fixed time"
    assert form["showScope"] is True
    assert [choice["label"] for choice in form["scopeChoices"]] == ["This day only", "Every Fri and Sat"]
    assert form["scope"] == "occurrence"
    sheets.setText("title", "Club night")
    sheets.setText("scope", "series")
    sheets.save()
    renamed = [item for item in shell.session.blocks if item["title"] == "Club night"]
    assert [item["days"] for item in renamed] == [[4, 5]]
    _settle(qapp, shell)

    sheets.editBlock(renamed[0]["id"], 4)
    sheets.setText("scope", "series")
    sheets.remove()
    assert sheets.ask["title"] == "Delete fixed time"
    assert sheets.ask["body"].startswith("Delete Club night on every Fri and Sat this week?")
    sheets.answer("delete")
    assert not [item for item in shell.session.blocks if item["title"] == "Club night"]
    assert sheets.notice == "Deleted Club night from this week."
    _settle(qapp, shell)


def test_deleting_a_setup_block_offers_this_week_or_every_week(shell: NativeWindow, sheets) -> None:
    sheets.editBlock("school", 0)
    sheets.remove()
    labels = [answer["label"] for answer in sheets.ask["answers"]]
    assert labels == ["Cancel", "This day only", "This week only", "This week and later"]
    sheets.answer("stay")
    assert any(item["id"] == "school" for item in shell.session.blocks)


def test_running_late_previews_then_accepts_through_the_session(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    before = len(shell.session.blocks)
    known = {item["id"] for item in shell.session.blocks}
    sheets.openLate()
    form = sheets.form
    assert sheets.kind == "late"
    assert form["heading"] == "Running late"
    assert form["intro"] == (
        "Say how late you are and preview what moves. Nothing changes until you accept it."
    )
    assert [choice["value"] for choice in form["choices"]] == [15, 30, 60]
    assert form["minutes"] == 30
    assert form["previewed"] is False
    assert form["context"].startswith("History essay,")
    assert form["context"].endswith("moves 30 min later")
    sheets.setLate(60)
    assert sheets.form["context"].endswith("moves 60 min later")
    sheets.setLate(30)
    sheets.preview()
    wait_until(qapp, lambda: shell.session.late_preview is not None)
    wait_until(qapp, lambda: sheets.form["previewed"] is True)
    assert sheets.form["changes"]
    assert any("History essay" in line for line in sheets.form["changes"])
    assert shell.session.late_preview is not None
    assert len(shell.session.blocks) == before
    sheets.acceptLate()
    assert sheets.kind == ""
    assert shell.session.late_preview is None
    assert len(shell.session.blocks) == before + 1
    late = next(item for item in shell.session.blocks if item["id"] not in known)
    assert late["duration_min"] == 30
    assert late["days"] == [3]
    _settle(qapp, shell)
    shell.session.undo()
    _settle(qapp, shell)


def test_cancelling_running_late_drops_the_preview(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    before = len(shell.session.blocks)
    sheets.openLate()
    sheets.preview()
    wait_until(qapp, lambda: shell.session.late_preview is not None)
    sheets.closeSheet()
    assert sheets.kind == ""
    assert shell.session.late_preview is None
    assert len(shell.session.blocks) == before


def test_more_rows_and_what_each_opens(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    shell._material_page.bridge.openMore()
    rows = {row["id"]: row for row in sheets.moreEntries if row["id"]}
    headings = [row["heading"] for row in sheets.moreEntries if row["heading"]]
    assert headings == ["Planning", "Help and info", "Account"]
    assert rows["runningLate"]["enabled"] is True
    # The essay has its time, so nothing is left over.
    assert rows["unfinishedOpen"]["enabled"] is False
    assert rows["unfinishedOpen"]["detail"] == "None left"
    for name in ("weekListRow", "routinesButton", "quickFocusAction", "replanAll", "helpButton", "signOut"):
        assert name in rows

    sheets.moreAction("runningLate")
    assert sheets.kind == "late"
    assert sheets.moreOpen is False
    sheets.forceClose()

    sheets.openMore()
    sheets.moreAction("weekListRow")
    assert sheets.kind == "weekList"
    items = [row for row in sheets.form["rows"] if row["type"] == "item"]
    school = [row for row in items if row["title"] == "School"]
    assert len(school) == 5
    assert school[0]["detail"].endswith("Fixed time")
    assert any(row["title"] == "History essay" for row in items)
    assert [row["text"] for row in sheets.form["rows"] if row["type"] == "heading"][0].startswith("Monday")
    block = next(item for item in shell.session.blocks if item.get("assignment_id") == "essay")
    sheets.openFromList(block["id"], 3)
    assert sheets.kind == "homework"
    assert sheets.form["title"] == "History essay"
    sheets.forceClose()

    sheets.openMore()
    sheets.moreAction("routinesButton")
    assert sheets.kind == "routines"
    assert sheets.form["empty"] == "No routines saved yet."
    sheets.forceClose()

    sheets.openMore()
    sheets.moreAction("unfinishedOpen")
    assert sheets.kind == ""
    sheets.closeMore()


def test_unfinished_lists_overdue_homework_and_delete_asks_first(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    session = shell.session
    monday = date.fromisoformat(session.week_start)
    session.add_homework(
        {
            "id": "lab-writeup",
            "title": "Lab write-up",
            "due": f"{session.week_start}T09:00",
            "estimate_min": 45,
            "revision": 0,
        }
    )
    session.save()
    _settle(qapp, shell)
    sheets.openMore()
    rows = {row["id"]: row for row in sheets.moreEntries if row["id"]}
    assert rows["unfinishedOpen"]["enabled"] is True
    assert rows["unfinishedOpen"]["detail"] != "None left"
    sheets.moreAction("unfinishedOpen")
    _pump(qapp)
    assert sheets.kind == "unfinished"
    found = next(row for row in sheets.form["rows"] if row["id"] == "lab-writeup")
    assert found["title"] == "Lab write-up"
    assert found["plannable"] is True
    assert found["overdue"] is True
    assert found["detail"].startswith("45 min left")
    assert f"due Mon {monday.day} {monday.strftime('%b')}" in found["detail"]
    assert found["detail"].endswith("Overdue")
    assert _find(shell._material_page.root, "planUnfinished-lab-writeup") is not None

    sheets.askDeleteUnfinished("lab-writeup")
    assert sheets.ask["title"] == "Delete homework"
    assert "Its times on the calendar go too, in every week." in sheets.ask["body"]
    sheets.answer("stay")
    assert "lab-writeup" in session.assignments
    sheets.askDeleteUnfinished("lab-writeup")
    sheets.answer("delete")
    wait_until(qapp, lambda: "lab-writeup" not in session.assignments)
    assert sheets.notice == "Deleted Lab write-up."
    _settle(qapp, shell)


def test_unfinished_find_a_time_plans_overdue_homework_through_the_session(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    session = shell.session
    session.add_homework(
        {
            "id": "overdue-quiz",
            "title": "Overdue quiz",
            "due": f"{session.week_start}T08:00",
            "estimate_min": 30,
            "revision": 0,
        }
    )
    session.save()
    _settle(qapp, shell)
    sheets.openUnfinished()
    sheets.findTime("overdue-quiz")
    wait_until(
        qapp,
        lambda: any(item.get("assignment_id") == "overdue-quiz" for item in session.blocks),
    )
    _settle(qapp, shell)


def _add_open_essay(qapp: QApplication, session) -> str:
    """Left from last week, due after the held Thursday clock, so Find a time still has minutes."""
    current = session.week_start
    previous = (date.fromisoformat(current) - timedelta(days=7)).isoformat()
    sunday = (date.fromisoformat(current) + timedelta(days=6)).isoformat()
    session.load_week(previous)
    wait_until(qapp, lambda: session.week_start == previous and not session.busy)
    session.add_homework(
        {
            "id": "open-essay",
            "title": "Open essay",
            "due": f"{sunday}T21:00",
            "estimate_min": 45,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy)
    session.load_week(current)
    wait_until(qapp, lambda: session.week_start == current and not session.busy)
    return "open-essay"


def _block_ids(session) -> set[str]:
    return {item["id"] for item in session.blocks}


def test_unfinished_find_a_time_leaves_non_overdue_blocks_unchanged_until_accept(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Homework that still has a deadline must wait for the Widgets preview's Accept."""
    session = shell.session
    current = session.week_start
    try:
        assignment_id = _add_open_essay(qapp, session)
    finally:
        if session.week_start != current:
            session.load_week(current)
            wait_until(qapp, lambda: session.week_start == current and not session.busy)
    before = _block_ids(session)
    opened: list[str] = []
    assert assignment_id not in session._overdue_assignment_ids()
    assert session.remaining_for(assignment_id) >= 15, session.assignments.get(assignment_id)
    assert session.plan_unfinished(assignment_id)

    def cancel(dialog: PreviewDialog) -> int:
        opened.append(dialog.objectName())
        assert _block_ids(session) == before
        assert not any(item.get("assignment_id") == assignment_id for item in session.blocks)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(PreviewDialog, "exec", cancel)
    sheets.openUnfinished()
    found = next(row for row in sheets.form["rows"] if row["id"] == assignment_id)
    assert found["overdue"] is False
    sheets.findTime(assignment_id)
    assert opened == ["stage3PreviewDialog"]
    assert _block_ids(session) == before
    assert not any(item.get("assignment_id") == assignment_id for item in session.blocks)

    def accept(dialog: PreviewDialog) -> int:
        opened.append(dialog.objectName())
        assert not any(item.get("assignment_id") == assignment_id for item in session.blocks)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(PreviewDialog, "exec", accept)
    sheets.findTime(assignment_id)
    wait_until(
        qapp,
        lambda: any(item.get("assignment_id") == assignment_id for item in session.blocks),
    )
    assert opened == ["stage3PreviewDialog", "stage3PreviewDialog"]
    _settle(qapp, shell)


def test_more_actions_press_the_widgets_buttons_they_name(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    pressed: list[str] = []
    fakes: dict[str, QPushButton] = {}

    def fake(name: str) -> QPushButton:
        if name not in fakes:
            button = QPushButton(name, shell)
            button.hide()
            button.clicked.connect(lambda _=False, which=name: pressed.append(which))
            fakes[name] = button
        return fakes[name]

    monkeypatch.setattr(sheets, "_button", fake)
    for name in ("quickFocusAction", "replanAll", "helpButton", "aboutButton", "signOut"):
        sheets.openMore()
        sheets.moreAction(name)
        assert sheets.moreOpen is False
    assert pressed == ["quickFocusAction", "replanAll", "helpButton", "aboutButton", "signOut"]
    fakes["helpButton"].setEnabled(False)
    sheets.openMore()
    sheets.moreAction("helpButton")
    assert pressed.count("helpButton") == 1
    sheets.closeMore()


def test_routines_apply_to_the_open_week_through_the_session(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    shell.session.routines["r-1"] = {
        "id": "r-1",
        "name": "Weekend",
        "revision": 1,
        "blocks": [
            {
                "template_id": "t1",
                "title": "Long walk",
                "days": [5],
                "start": "10:00",
                "duration_min": 60,
                "category": "exercise",
            }
        ],
    }
    try:
        sheets.openRoutines()
        _pump(qapp)
        assert sheets.form["intro"] == "Pick a routine, the week to copy it into and the days to copy."
        assert sheets.form["rows"][0]["name"] == "Weekend"
        assert sheets.form["rows"][0]["detail"] == "1 fixed times"
        assert _find(shell._material_page.root, "routinesApply").property("text") == "Apply"
        sheets.applyRoutine()
        assert sheets.form["error"] == "Choose a saved routine."
        sheets.selectRoutine("r-1")
        assert [day["on"] for day in sheets.form["days"]] == [False] * 5 + [True, False]
        sheets.toggleRoutineDay(5)
        sheets.applyRoutine()
        assert sheets.form["error"] == "Choose at least one weekday to copy."
        sheets.toggleRoutineDay(5)
        sheets.applyRoutine()
        wait_until(qapp, lambda: sheets.kind == "")
        assert any(item["title"] == "Long walk" for item in shell.session.blocks)
        assert sheets.notice == "Added the Weekend routine."
        _settle(qapp, shell)
    finally:
        shell.session.routines.pop("r-1", None)


def test_a_sheet_in_qml_is_a_dialog_on_a_desktop_and_a_bottom_sheet_on_a_phone(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = _show_material(qapp, shell)
    sheets.openHomework()
    _pump(qapp)
    card = _find(root, "sheetCard")
    assert int(card.property("width")) == 560
    assert _find(root, "homeworkTitle") is not None
    assert _find(root, "homeworkNext").property("accessName") == "Next"
    sheets.forceClose()
    _pump(qapp)

    shell.setMinimumWidth(360)
    shell.resize(700, 800)
    _pump(qapp)
    try:
        sheets.openHomework()
        _pump(qapp)
        card = _find(root, "sheetCard")
        assert int(card.property("width")) == int(root.property("width")) == 700
        assert float(card.property("y")) + float(card.property("height")) == pytest.approx(
            float(root.property("height"))
        )
        sheets.forceClose()
    finally:
        shell.setMinimumWidth(WINDOW_MIN_WIDTH)
        shell.resize(1280, 800)
        _pump(qapp)


def test_esc_closes_a_sheet_and_the_keyboard_goes_back_to_the_add_button(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = _show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    fab = _qml(root, "materialFab")
    fab.forceActiveFocus()
    _pump(qapp)
    sheets.openHomework()
    _pump(qapp, 60)
    held = quick.quickWindow().activeFocusItem()
    assert held is not None
    assert held.objectName() != "materialFab"
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    _pump(qapp)
    assert sheets.kind == ""
    assert quick.quickWindow().activeFocusItem() is fab


def test_the_discard_prompt_shows_in_qml_and_esc_keeps_editing(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = _show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    sheets.openHomework()
    _type_homework(sheets, "Typed")
    _pump(qapp, 60)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    _pump(qapp, 40)
    assert sheets.ask["title"] == DISCARD
    assert _find(root, "prompt_keep") is not None
    assert _find(root, "prompt_discard") is not None
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    _pump(qapp, 40)
    assert sheets.ask == {}
    assert sheets.kind == "homework"


def _hold_changes(
    session, monkeypatch: pytest.MonkeyPatch, trace: list[str] | None = None
) -> tuple[list, object]:
    original = session.client.request
    held: list = []

    def delay(method, path, body, ok, fail):
        if method == "POST" and path == "/api/changes":
            if trace is not None:
                trace.append("post")

            def tracked_ok(data):
                if trace is not None:
                    trace.append("ok")
                ok(data)

            def tracked_fail(error):
                if trace is not None:
                    trace.append("fail")
                fail(error)

            held.append((method, path, body, tracked_ok, tracked_fail))
        else:
            original(method, path, body, ok, fail)

    monkeypatch.setattr(session.client, "request", delay)
    return held, original


def _deliver_held_change(qapp: QApplication, shell: NativeWindow, held: list, original) -> None:
    """Send one held POST through the real client, then wait for that retry to finish."""
    assert held, "the held POST never left"
    original(*held.pop(0))
    wait_until(qapp, lambda: not shell.session.busy and not shell.session.dirty)


def _restore_essay(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    if shell.session.assignments.get("essay", {}).get("title") == "History essay":
        return
    sheets.editHomework("essay")
    sheets.setText("title", "History essay")
    sheets.save()
    _settle(qapp, shell)


def test_a_second_homework_save_keeps_the_draft_while_the_first_is_pending(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = shell.session
    held, original = _hold_changes(session, monkeypatch)
    try:
        sheets.editHomework("essay")
        sheets.setText("title", "First saved title")
        sheets.save()
        assert session.busy and len(held) == 1
        assert held[0][2]["assignments"][0]["assignment"]["title"] == "First saved title"
        sheets.editHomework("essay")
        sheets.setText("title", "Second saved title")
        sheets.save()
        assert sheets.kind == "homework"
        assert sheets.form["title"] == "Second saved title"
        assert sheets.canSave is False
        assert sheets.notice == WAIT_SAVE
        assert session.assignments["essay"]["title"] == "First saved title"
        monkeypatch.setattr(session.client, "request", original)
        original(*held.pop())
        _settle(qapp, shell)
        assert session.assignments["essay"]["title"] == "First saved title"
        assert session.pending_save is None
        assert not session.dirty
        assert sheets.kind == "homework"
        assert sheets.form["title"] == "Second saved title"
        assert sheets.canSave is True
        sheets.save()
        _settle(qapp, shell)
        assert session.assignments["essay"]["title"] == "Second saved title"
        assert not session.dirty and session.pending_save is None
    finally:
        monkeypatch.setattr(session.client, "request", original)
        while held:
            original(*held.pop(0))
        _settle(qapp, shell)
        sheets.forceClose()
        _restore_essay(qapp, shell, sheets)


def test_a_failed_first_save_leaves_the_second_draft_and_pending_first(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = shell.session
    trace: list[str] = []
    held, original = _hold_changes(session, monkeypatch, trace)
    try:
        sheets.editHomework("essay")
        sheets.setText("title", "First saved title")
        sheets.save()
        sheets.editHomework("essay")
        sheets.setText("title", "Second saved title")
        sheets.save()
        assert sheets.form["title"] == "Second saved title"
        assert trace == ["post"]
        _method, _path, first_body, _ok, fail = held.pop(0)
        fail(ApiError(503, "The planner is unavailable."))
        _pump(qapp)
        # Window autosave (500 ms) can post the same pending payload during _pump. That is
        # the retry; unpatching and waiting 8s on retry_save() left it held and busy.
        assert trace[:2] == ["post", "fail"]
        assert session.assignments["essay"]["title"] == "First saved title"
        assert session.pending_save is not None
        assert session.can_undo() is False
        assert sheets.kind == "homework"
        assert sheets.form["title"] == "Second saved title"
        assert sheets.canSave is False
        session.retry_save()
        wait_until(qapp, lambda: len(held) >= 1)
        assert session.pending_save is not None
        assert sheets.form["title"] == "Second saved title"
        assert held[0][2]["operation_id"] == first_body["operation_id"]
        _deliver_held_change(qapp, shell, held, original)
        assert trace == ["post", "fail", "post", "ok"]
        assert session.assignments["essay"]["title"] == "First saved title"
        assert session.pending_save is None
        sheets.save()
        assert held[0][2]["operation_id"] != first_body["operation_id"]
        _deliver_held_change(qapp, shell, held, original)
        assert session.assignments["essay"]["title"] == "Second saved title"
        assert trace == ["post", "fail", "post", "ok", "post", "ok"]
        session.reload()
        _settle(qapp, shell)
        assert session.assignments["essay"]["title"] == "Second saved title"
    finally:
        monkeypatch.setattr(session.client, "request", original)
        while held:
            original(*held.pop(0))
        _settle(qapp, shell)
        sheets.forceClose()
        _restore_essay(qapp, shell, sheets)


def test_a_block_save_and_delete_wait_while_a_save_is_pending(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = shell.session
    held, original = _hold_changes(session, monkeypatch)
    try:
        sheets.editHomework("essay")
        sheets.setText("title", "Pending essay")
        sheets.save()
        assert session.busy
        sheets.editBlock("school", 0)
        sheets.setText("title", "Homeroom")
        sheets.save()
        assert sheets.kind == "block"
        assert sheets.form["title"] == "Homeroom"
        assert sheets.notice == WAIT_SAVE
        school = next(item for item in session.blocks if item["id"] == "school")
        assert school["title"] == "School"
        sheets.remove()
        sheets.answer("week")
        assert sheets.kind == "block"
        assert sheets.notice == WAIT_DELETE
        assert any(item["id"] == "school" for item in session.blocks)
    finally:
        monkeypatch.setattr(session.client, "request", original)
        while held:
            original(*held.pop(0))
        _settle(qapp, shell)
        sheets.forceClose()
        _restore_essay(qapp, shell, sheets)


GENERIC_FOCUS = {
    "",
    "fieldInput",
    "shape",
    "label",
    "pickerValue",
    "pickerList",
    "sheetBody",
    "sheetCard",
    "sheetHost",
    "sheetTitle",
    "homeworkSheet",
    "blockSheet",
    "lateSheet",
    "homeworkDetails",
    "homeworkPrompt",
    "blockPrompt",
    "materialShell",
    "promptCard",
    "savePrompt",
    "importPrompt",
    "exportPrompt",
    "presetPrompt",
    "sheetPrompt",
}
SHEET_OWNERS = (
    "sheetHost",
    "homeworkSheet",
    "blockSheet",
    "lateSheet",
    "sheetCard",
    "sheetPrompt",
    "pickerList",
)
UNDERLAY = (
    "weekBlock",
    "homeworkCard",
    "navWeek",
    "navDay",
    "navMonth",
    "navMyDay",
    "navSettings",
    "materialFab",
    "materialSnackbar",
    "materialRail",
    "materialUndo",
    "materialRedo",
    "materialMore",
    "weekPrevious",
    "weekNext",
)
HIDDEN_ON_HOMEWORK_EDIT = (
    "homeworkBack",
    "homeworkDueTimePhone",
    "homeworkCourse",
    "homeworkNotes",
    "homeworkCrumb0",
)


def _lineage(item: QObject | None) -> list[str]:
    names: list[str] = []
    while item is not None:
        names.append(str(item.objectName() or type(item).__name__))
        item = item.parentItem() if hasattr(item, "parentItem") else None
    return names


def _focused(shell: NativeWindow) -> QObject | None:
    return shell._material_page._quick.quickWindow().activeFocusItem()


def _semantic(chain: list[str]) -> str:
    for name in chain:
        if name.startswith("QQuick"):
            continue
        if name in GENERIC_FOCUS:
            continue
        return name
    return chain[0] if chain else "(none)"


def _press(qapp: QApplication, shell: NativeWindow, key: Qt.Key) -> list[str]:
    QTest.keyClick(shell._material_page._quick, key)
    _pump(qapp, 3)
    return _lineage(_focused(shell))


def _item_enabled(item: QObject | None) -> bool:
    while item is not None:
        value = item.property("enabled") if hasattr(item, "property") else None
        if value is False:
            return False
        item = item.parentItem() if hasattr(item, "parentItem") else None
    return True


def _week_marks(shell: NativeWindow) -> tuple:
    return tuple(
        (
            str(block.get("id")),
            block.get("start"),
            tuple(block.get("days") or []),
            bool(block.get("completed")),
        )
        for block in shell.session.blocks
    )


def _cycle_names(
    qapp: QApplication, shell: NativeWindow, start: str, key: Qt.Key, owners: tuple[str, ...]
) -> list[str]:
    names: list[str] = []
    for _ in range(24):
        chain = _press(qapp, shell, key)
        name = _semantic(chain)
        assert any(owner in chain for owner in owners), f"{key} left the overlay at {name}: {chain}"
        assert not any(leak in chain for leak in UNDERLAY), f"{key} reached the underlay: {chain}"
        assert _item_enabled(_focused(shell)), f"{name} was not enabled: {chain}"
        if not names:
            assert name != start, f"{key} did not leave {start}: {chain}"
        if name == start:
            return names
        names.append(name)
    raise AssertionError(f"{key} never wrapped back to {start}; visited {names}")


def test_homework_sheet_tab_cycles_enabled_controls_and_wraps_both_ways(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = shell._material_page.root
    nav = _qml(root, "navWeek")
    nav.forceActiveFocus()
    _pump(qapp)
    marks = _week_marks(shell)
    done = bool(shell.session.assignments["essay"].get("completed"))
    screen = shell._material_page.bridge.property("screen")
    sheets.editHomework("essay")
    _pump(qapp)
    assert sheets.kind == "homework"
    start_chain = _lineage(_focused(shell))
    start = _semantic(start_chain)
    assert start == "homeworkTitle", f"initial focus was {start}: {start_chain}"
    assert "homeworkSheet" in start_chain
    essay = next(block for block in _named(root, "weekBlock") if block.property("title") == "History essay")
    assert essay.property("enabled") is False
    assert _qml(root, "materialFab").property("enabled") is False

    forward = _cycle_names(qapp, shell, start, Qt.Key.Key_Tab, SHEET_OWNERS)
    assert len(forward) == len(set(forward)), f"Tab repeated a control: {forward}"
    assert len(forward) >= 8, f"Tab visited too few controls: {forward}"
    for name in (
        "homeworkDue",
        "homeworkDueTime",
        "homeworkWhen",
        "homeworkQuick",
        "homeworkCompleted",
        "homeworkMoreDetails",
        "deleteHomework",
        "homeworkCancel",
        "homeworkNext",
    ):
        assert name in forward, f"{name} missing from {forward}"
    for name in HIDDEN_ON_HOMEWORK_EDIT:
        assert name not in forward, f"hidden {name} was in {forward}"

    backward = _cycle_names(qapp, shell, start, Qt.Key.Key_Backtab, SHEET_OWNERS)
    assert backward == list(reversed(forward)), f"Backtab {backward} was not the reverse of {forward}"
    assert _semantic(_lineage(_focused(shell))) == start
    assert _week_marks(shell) == marks
    assert bool(shell.session.assignments["essay"].get("completed")) is done
    assert shell._material_page.bridge.property("screen") == screen

    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Escape)
    _pump(qapp, 8)
    assert sheets.kind == ""
    restored = _lineage(_focused(shell))
    assert "navWeek" in restored
    assert essay.property("enabled") is True
    assert _qml(root, "materialFab").property("enabled") is True
    assert _week_marks(shell) == marks

    sheets.editHomework("essay")
    _pump(qapp)
    due = _find(root, "homeworkDue")
    due.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Space)
    _pump(qapp, 8)
    scene = shell._material_page._quick.quickWindow().contentItem()
    lists = [item for item in _visuals(scene) if str(item.objectName()) == "pickerList"]
    assert lists, f"due picker did not open; focus={_lineage(_focused(shell))}"
    for index in range(4):
        chain = _press(qapp, shell, Qt.Key.Key_Tab)
        assert "pickerList" in chain or "Popup" in chain, f"picker Tab {index} left the list: {chain}"
        assert "weekBlock" not in chain
        assert "homeworkNext" not in chain
        assert "navWeek" not in chain
    sheets.forceClose()
    _pump(qapp, 5)


def test_fixed_time_sheet_tab_wraps_inside_and_skips_hidden_controls(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    marks = _week_marks(shell)
    sheets.editBlock("school", 0)
    _pump(qapp)
    assert sheets.kind == "block"
    start_chain = _lineage(_focused(shell))
    start = _semantic(start_chain)
    assert start == "blockTitle", f"initial focus was {start}: {start_chain}"
    forward = _cycle_names(qapp, shell, start, Qt.Key.Key_Tab, SHEET_OWNERS)
    assert len(forward) == len(set(forward)), f"Tab repeated a control: {forward}"
    assert len(forward) >= 5, f"Tab visited too few controls: {forward}"
    for name in ("blockCancel", "blockNext"):
        assert name in forward, f"{name} missing from {forward}"
    assert "blockBack" not in forward
    backward = _cycle_names(qapp, shell, start, Qt.Key.Key_Backtab, SHEET_OWNERS)
    assert backward == list(reversed(forward)), f"Backtab {backward} was not the reverse of {forward}"
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Escape)
    _pump(qapp, 5)
    assert sheets.kind == ""
    assert _week_marks(shell) == marks


def _open_from_more(qapp: QApplication, shell: NativeWindow, sheets, action: str) -> None:
    shell.activateWindow()
    shell._material_page._quick.setFocus()
    _qml(shell._material_page.root, "materialFab").forceActiveFocus()
    _pump(qapp)
    sheets.openMore()
    _pump(qapp, 10)
    sheets.moreAction(action)
    _pump(qapp, 10)


def test_running_late_from_more_takes_the_keyboard_and_tab_stays_in_the_sheet(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _open_from_more(qapp, shell, sheets, "runningLate")
    assert sheets.kind == "late"
    chain = _lineage(_focused(shell))
    assert "lateMinutes" in chain, chain
    chain = _press(qapp, shell, Qt.Key.Key_Tab)
    assert "lateSheet" in chain and "lateMinutes" not in chain, chain


def test_unfinished_from_more_takes_the_keyboard(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    session = shell.session
    session.add_homework(
        {
            "id": "lab-writeup",
            "title": "Lab write-up",
            "due": f"{session.week_start}T09:00",
            "estimate_min": 45,
            "revision": 0,
        }
    )
    session.save()
    _settle(qapp, shell)
    _open_from_more(qapp, shell, sheets, "unfinishedOpen")
    assert sheets.kind == "unfinished"
    assert "unfinishedSheet" in _lineage(_focused(shell))
    assert "unfinishedSheet" in _press(qapp, shell, Qt.Key.Key_Tab)


def _open_pinned_time_field(qapp: QApplication, shell: NativeWindow, sheets):
    sheets.editHomework("essay")
    _pump(qapp)
    sheets.setText("when", "fixed")
    sheets.setText("whenTime", "19:00")
    _pump(qapp)
    root = shell._material_page._quick.rootObject()
    field = _find(root, "homeworkWhenTime")
    field.forceActiveFocus()
    _pump(qapp)
    return field


def test_pinned_time_list_opens_on_the_chosen_time(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    _open_pinned_time_field(qapp, shell, sheets)
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Space)
    _pump(qapp, 8)
    scene = shell._material_page._quick.quickWindow().contentItem()
    lists = [item for item in _visuals(scene) if str(item.objectName()) == "pickerList"]
    assert lists, "the pinned time list did not open"
    picker = lists[0]
    seven_pm = 19 * 4
    assert picker.property("currentIndex") == seven_pm
    top = picker.property("contentY")
    assert top <= seven_pm * 44 < top + picker.property("height"), (
        f"7:00 PM (row {seven_pm}) is off screen: the list starts at {top}"
    )
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Escape)
    _pump(qapp, 5)
    sheets.forceClose()
    _pump(qapp, 5)


def test_pinned_time_moves_with_up_and_down_on_the_closed_field(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _open_pinned_time_field(qapp, shell, sheets)
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Up)
    _pump(qapp, 5)
    assert sheets.form["whenTime"] == "18:45"
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Down)
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Down)
    _pump(qapp, 5)
    assert sheets.form["whenTime"] == "19:15"
    sheets.forceClose()
    _pump(qapp, 5)
