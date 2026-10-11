"""The rig's --play file: what it accepts, what it refuses and says, and where its output goes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.rig import drive, play

DESIGNS = ("classic", "bento", "one")
LOOKS = ("terminal", "dark-frost")


def _parse(raw: object, name: str = "p") -> play.Play:
    return play.parse_play(raw, name, DESIGNS, LOOKS)


def test_a_full_play_reads_as_written():
    got = _parse(
        {
            "setup": {
                "clock": "2026-10-15T17:00",
                "seed": "setup-done",
                "size": [1000, 700],
                "design": "bento",
                "clock_24h": True,
                "text": "large",
                "look": "terminal",
            },
            "steps": [
                {"click": "addArrow"},
                {"click": {"text": "Add fixed time"}},
                {"double_click": [10, 20]},
                {"right_click": "weekCell"},
                {"drag": ["chip", [300, 400]]},
                {"type": "Band practice"},
                {"key": "shift+Tab"},
                {"wait": 500},
                {"advance_clock": 30},
                {"shot": "after-tab"},
                {"tree": "after-tab"},
                {"say": "the title box lost focus"},
            ],
        },
        name="mine",
    )
    assert got.name == "mine"
    assert got.setup == play.Setup(
        clock=datetime(2026, 10, 15, 17, 0),
        seed="setup-done",
        size=(1000, 700),
        design="bento",
        clock_24h=True,
        text="large",
        look="terminal",
    )
    assert [step.action for step in got.steps] == [
        "click",
        "click",
        "double_click",
        "right_click",
        "drag",
        "type",
        "key",
        "wait",
        "advance_clock",
        "shot",
        "tree",
        "say",
    ]
    assert got.steps[0].value == ("name", "addArrow")
    assert got.steps[1].value == ("text", "Add fixed time")
    assert got.steps[2].value == ("point", (10, 20))
    assert got.steps[4].value == (("name", "chip"), ("point", (300, 400)))


def test_a_play_with_no_setup_gets_the_rigs_own_defaults():
    got = _parse({"steps": []})
    assert got.setup == play.Setup()
    assert (got.setup.seed, got.setup.design, got.setup.size) == ("rig", "classic", (1280, 800))
    assert got.setup.clock is None
    assert got.steps == ()


@pytest.mark.parametrize(
    ("step", "says"),
    [
        ({"hover": "x"}, "'hover' is not an action"),
        ({"click": "a", "key": "Tab"}, "one action"),
        ("click", "one action"),
        ({"click": ""}, "empty objectName"),
        ({"click": [1]}, "[x, y]"),
        ({"click": [-1, 5]}, "[x, y]"),
        ({"click": [1.5, 5]}, "[x, y]"),
        ({"click": {"label": "Add"}}, '"text"'),
        ({"drag": ["a"]}, "[from, to]"),
        ({"drag": [10, 20]}, "[[x1, y1], [x2, y2]]"),
        ({"type": ""}, "words to type"),
        ({"key": "-Tab"}, "shift+Tab"),
        ({"key": "ctrl+"}, "shift+Tab"),
        ({"key": "a b"}, "shift+Tab"),
        ({"wait": -1}, "milliseconds"),
        ({"wait": 60001}, "milliseconds"),
        ({"wait": "5"}, "milliseconds"),
        ({"advance_clock": 0}, "whole minutes"),
        ({"advance_clock": 10081}, "whole minutes"),
        ({"shot": "has space"}, "label"),
        ({"tree": "../x"}, "label"),
        ({"say": "  "}, "needs a note"),
    ],
)
def test_a_bad_step_is_named_with_its_number(step, says):
    with pytest.raises(play.PlayError) as refused:
        _parse({"steps": [{"wait": 1}, step]})
    assert refused.value.args[0].startswith("step 2: ")
    assert says in str(refused.value)


@pytest.mark.parametrize(
    ("setup", "says"),
    [
        ({"clock": "tomorrow"}, "setup clock"),
        ({"clock": 5}, "setup clock"),
        ({"seed": "full"}, "rig, empty, setup-done"),
        ({"design": "mission"}, "classic, bento, one"),
        ({"text": "huge"}, "normal, large"),
        ({"look": "default"}, "terminal, dark-frost"),
        ({"clock_24h": "yes"}, "true or false"),
        ({"size": [1280]}, "[width, height]"),
        ({"size": [100, 100]}, "between 640x480 and 3840x2160"),
        ({"zoom": 2}, "Setup keys: clock, seed, size, design, clock_24h, text, look"),
    ],
)
def test_a_bad_setup_value_is_named(setup, says):
    with pytest.raises(play.PlayError) as refused:
        _parse({"setup": setup, "steps": []})
    assert says in str(refused.value)


def test_every_mistake_is_reported_at_once_not_one_per_run():
    with pytest.raises(play.PlayError) as refused:
        _parse({"setup": {"seed": "full"}, "steps": [{"key": "-x"}, {"wait": 5}, {"nap": 1}], "extra": 1})
    lines = str(refused.value).splitlines()
    assert len(lines) == 4
    assert any(line.startswith("step 1: ") for line in lines)
    assert any(line.startswith("step 3: ") for line in lines)
    assert any("setup seed" in line for line in lines)
    assert any("'extra' is not a play key" in line for line in lines)


@pytest.mark.parametrize("raw", [[], "play", None, {"steps": "click"}, {"setup": 1, "steps": []}])
def test_a_play_that_is_not_the_right_shape_is_refused(raw):
    with pytest.raises(play.PlayError):
        _parse(raw)


def test_load_names_unreadable_and_broken_files(tmp_path):
    with pytest.raises(play.PlayError, match="Cannot read"):
        play.load_play(tmp_path / "missing.json", DESIGNS, LOOKS)
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    with pytest.raises(play.PlayError, match="is not valid JSON"):
        play.load_play(broken, DESIGNS, LOOKS)
    good = tmp_path / "walk.json"
    good.write_text(json.dumps({"steps": [{"shot": "start"}]}))
    assert play.load_play(good, DESIGNS, LOOKS).name == "walk"


@pytest.mark.parametrize(
    ("wanted", "shown", "score"),
    [
        ("Add fixed time", "Add fixed time…", 2),
        ("add fixed time", "&Add fixed time...", 2),
        ("Save", "<b>Save</b>", 2),
        ("Add", "Add fixed time…", 1),
        ("Delete", "Add fixed time…", 0),
        ("Add", "", 0),
    ],
)
def test_text_targets_match_the_words_a_student_reads(wanted, shown, score):
    assert play.matches_words(wanted, shown) == score


def test_a_play_without_an_out_folder_writes_under_the_scratch_plays_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    folder = play.default_play_folder("my play/1", datetime(2026, 10, 11, 9, 5, 7))
    assert folder == tmp_path / ".flexweek-ui-harness" / "scratch" / "plays" / "20261011-090507-my-play-1"


def test_the_names_a_play_may_use_for_looks_are_the_apps_own():
    names = drive.play_looks()
    assert "terminal" in names
    assert "dark-frost" in names
    assert "default" not in names


def _args(**changes) -> argparse.Namespace:
    base = {"play": None, "design": None, "tab": None, "scenario": None, "option": [], "list": False}
    return argparse.Namespace(**{**base, **changes})


@pytest.mark.parametrize("flag", ["design", "tab", "scenario", "option", "list"])
def test_a_play_does_not_mix_with_the_scenario_flags(flag, tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"steps": []}))
    value = ["a=b"] if flag == "option" else (True if flag == "list" else "x")
    with pytest.raises(SystemExit) as refused:
        drive.check_play(_args(play=str(path), **{flag: value}))
    assert "do not mix" in str(refused.value)


def test_a_bad_play_stops_before_any_session_starts_and_names_the_file(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"steps": [{"key": "-x"}]}))
    with pytest.raises(SystemExit) as refused:
        drive.check_play(_args(play=str(path)))
    assert str(refused.value).startswith(f"{path}:\nstep 1: ")


def test_a_good_play_path_is_made_absolute_for_the_child(tmp_path, monkeypatch):
    (tmp_path / "p.json").write_text(json.dumps({"steps": []}))
    monkeypatch.chdir(tmp_path)
    args = _args(play="p.json")
    drive.check_play(args)
    assert args.play == str(tmp_path / "p.json")
