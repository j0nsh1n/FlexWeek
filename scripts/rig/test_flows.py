"""The flows recorded as clips (spec.md, Testing structure rule 6): each in Material 3,
and every file a play the rig accepts."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.rig import play

FLOWS = Path(__file__).with_name("flows")
# The actions rule 6 lists.
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


def test_every_flow_is_recorded_in_material():
    found = {path.stem for path in FLOWS.glob("*.json")}
    assert found == {f"{flow}.material" for flow in EXPECTED}


PLAYS = Path(__file__).with_name("plays")
WIDGETS_TARGETS = {"settingsGear", "chooseMaterial", "useWidgets"}
EVERY_FILE = sorted([*PLAYS.glob("*.json"), *FLOWS.glob("*.json")])


@pytest.mark.parametrize("path", EVERY_FILE, ids=lambda path: f"{path.parent.name}/{path.stem}")
def test_a_play_or_flow_starts_on_material_and_never_goes_through_widgets(path):
    got = play.load_play(path)
    clicked = {step.value[1] for step in got.steps if step.action == "click" and step.value[0] == "name"}
    seen = {step.value for step in got.steps if step.action == "see"}
    assert not (clicked | seen) & WIDGETS_TARGETS


@pytest.mark.parametrize("path", sorted(FLOWS.glob("*.json")), ids=lambda path: path.stem)
def test_a_flow_is_a_play_the_rig_accepts(path):
    got = play.load_play(path)
    assert got.steps, "a flow does something"
    assert any(step.action == "shot" for step in got.steps), "a flow photographs what it did"
