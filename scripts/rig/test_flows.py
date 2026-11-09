"""The flows recorded as clips (spec.md, Testing structure rule 6): each in Widgets and in Material 3,
and every file a play the rig accepts."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.rig import drive, play

FLOWS = Path(__file__).with_name("flows")
# The actions rule 6 lists as meant to behave the same in Widgets and Material 3.
EXPECTED = {
    "add-homework",
    "done-and-undo",
    "open-and-edit",
    "drag-a-block",
    "plan-my-homework",
    "running-late",
    "focus",
    "switch-views",
    "change-look",
}


def test_every_flow_is_recorded_in_widgets_and_material():
    found = {path.stem for path in FLOWS.glob("*.json")}
    assert found == {f"{flow}.{surface}" for flow in EXPECTED for surface in ("widgets", "material")}


@pytest.mark.parametrize("path", sorted(FLOWS.glob("*.json")), ids=lambda path: path.stem)
def test_a_flow_is_a_play_the_rig_accepts(path):
    got = play.load_play(path, (*drive.DESIGNS, *drive.MY_DAY), drive.play_looks())
    assert got.steps, "a flow does something"
    assert any(step.action == "shot" for step in got.steps), "a flow photographs what it did"
