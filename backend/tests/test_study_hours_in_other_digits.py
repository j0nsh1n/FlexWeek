"""A study-hours start typed in another script's digits is accepted by the model and read as Python's
int() reads it. The planner's own check of the same rule is in
engine/engine/tests/test_stage4_availability.rs."""

from __future__ import annotations

from backend import availability as live_availability
from backend import models as live_models


def test_a_window_start_in_other_digits_is_read_as_int_reads_it():
    # The pattern's `\d` takes "1٠" and int() reads it as 10, so the window runs 10:00 to 12:00.
    body = {"days": [0], "start": "1٠:00", "end": "12:00"}
    live = [live_models.WorkWindow(**body)]
    for start_min, rank in ((10 * 60, 1), (0, 2)):
        assert live_availability.study_rank(live, None, 0, start_min, 60) == rank
