"""The week can start on any of the seven days. The choice is kept per computer, and the engine counts it
0 Monday to 6 Sunday. Stored weeks stay keyed by their Monday either way."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from desktop.native import fields


@pytest.fixture()
def kept(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """The per-computer file, in a temporary folder for each test."""
    path = tmp_path / "week-start.json"
    monkeypatch.setattr(fields, "_week_starts_file", lambda: path)
    return path


def test_a_new_computer_starts_the_week_on_monday(kept: Path) -> None:
    assert fields.week_starts_on() == "monday"
    assert fields.week_start_day() == 0


@pytest.mark.parametrize(
    ("start", "day"),
    (
        ("tuesday", 1),
        ("wednesday", 2),
        ("thursday", 3),
        ("friday", 4),
        ("saturday", 5),
        ("sunday", 6),
    ),
)
def test_any_weekday_can_be_saved_and_is_counted_from_monday(kept: Path, start: str, day: int) -> None:
    fields.save_week_starts_on(start)
    assert fields.week_starts_on() == start
    assert fields.week_start_day() == day


def test_a_damaged_week_start_file_falls_back_to_monday(kept: Path) -> None:
    kept.write_text("{not json", encoding="utf-8")
    assert fields.week_starts_on() == "monday"
    kept.write_text('{"week_starts_on": "someday"}', encoding="utf-8")
    assert fields.week_starts_on() == "monday"


def test_a_file_written_before_any_day_could_be_picked_still_reads(kept: Path) -> None:
    kept.write_text('{"week_starts_on":"sunday"}', encoding="utf-8")
    assert fields.week_starts_on() == "sunday"


def test_only_the_seven_day_names_can_be_saved(kept: Path) -> None:
    for wrong in ("someday", "Wednesday", ""):
        with pytest.raises(ValueError):
            fields.save_week_starts_on(wrong)
    assert not kept.exists()
