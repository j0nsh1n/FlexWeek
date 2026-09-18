"""Undo snapshots for the native week. Expected values are the before/after blocks."""

from __future__ import annotations

from desktop.native.history import HISTORY_LIMIT, capture_step, mark_stale, push_step


def test_capture_step_records_only_what_changed() -> None:
    before = [{"id": "soccer", "title": "Soccer"}]
    after = [{"id": "soccer", "title": "Soccer"}, {"id": "piano", "title": "Piano"}]
    step = capture_step("editing Piano", "2026-09-07", before, after, {}, {}, set())
    assert step is not None
    assert step["label"] == "editing Piano"
    assert step["weeks"][0]["before"] == before
    assert step["weeks"][0]["after"] == after
    assert step["assignments"] == []


def test_capture_step_skips_an_unchanged_week() -> None:
    blocks = [{"id": "soccer", "title": "Soccer"}]
    assert capture_step("editing", "2026-09-07", blocks, blocks, {}, {}, set()) is None


def test_capture_step_records_a_new_assignment() -> None:
    homework = {"id": "lab", "title": "Lab", "due": "2026-09-11T08:10"}
    step = capture_step(
        "editing Lab",
        "2026-09-07",
        [],
        [],
        {},
        {"lab": homework},
        {"lab"},
    )
    assert step is not None
    assert step["assignments"] == [
        {"id": "lab", "before": None, "after": homework},
    ]


def test_push_step_drops_the_oldest_past_the_limit() -> None:
    stack: list[dict] = []
    for index in range(HISTORY_LIMIT + 2):
        push_step(stack, {"label": str(index), "weeks": [], "assignments": [], "stale": False})
    assert len(stack) == HISTORY_LIMIT
    assert stack[0]["label"] == "2"
    assert stack[-1]["label"] == str(HISTORY_LIMIT + 1)


def test_mark_stale_only_touches_steps_for_that_week() -> None:
    steps = [
        {"weeks": [{"week_start": "2026-09-07"}], "stale": False},
        {"weeks": [{"week_start": "2026-09-14"}], "stale": False},
    ]
    mark_stale(steps, "2026-09-07")
    assert steps[0]["stale"] is True
    assert steps[1]["stale"] is False
