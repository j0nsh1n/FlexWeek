"""Month cells name the work, they do not count it."""

from desktop.native.calendar import month_chips


def test_due_homework_is_a_named_chip() -> None:
    cell = {"date": "2026-09-17", "due_ids": ["chem"]}
    snapshot = {
        "deadlines": [{"id": "chem", "title": "Chem lab report", "category": "assignments"}],
        "overdue": [],
    }
    assert month_chips(cell, snapshot, []) == [("Chem lab report", "assignments")]


def test_the_open_week_adds_what_is_already_on_that_date() -> None:
    cell = {"date": "2026-09-17", "due_ids": []}
    placed = [("2026-09-17", "School", "class"), ("2026-09-18", "Soccer", "exercise")]
    assert month_chips(cell, {"deadlines": [], "overdue": []}, placed) == [("School", "class")]
