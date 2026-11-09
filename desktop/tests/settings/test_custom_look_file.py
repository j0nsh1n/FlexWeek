"""A look file may hold anything; the look keeps what it can, says what it left out and never crashes."""

from __future__ import annotations

from desktop.native.custom_look import import_look
from desktop.native.look import resolved_palette, sanitize_custom, sanitize_look


def test_unknown_settings_and_bad_values_are_dropped_and_said_never_a_crash() -> None:
    raw = {
        "base": "paper",
        "wallpaper": "cats",
        "accent": "chartreuse",
        "colours": {"page": "#fffff", "text": "#123456", "glow": "#ffffff"},
        "categories": {"class": {"hue": "blue"}, "robots": {"hue": 10}, "study": {"hue": 300}},
        "corners": 40,
        "text_scale": "big",
        "spacing": "roomy",
        "show_times": "yes",
        "name": "  Late   night  ",
    }
    clean, problems = sanitize_custom(raw)
    assert clean == {
        "base": "paper",
        "name": "Late night",
        "colours": {"text": "#123456"},
        "categories": {"study": {"hue": 300.0}},
    }
    assert len(problems) == 10, problems
    assert any("wallpaper" in problem for problem in problems)
    for broken in (
        None,
        [],
        "paper",
        {"base": "neon"},
        {"base": ["light"]},
        {"base": "light", "colours": 3},
        {"base": "light", "categories": "all"},
        {"base": "light", "corners": float("nan")},
    ):
        try:
            sanitize_custom(broken)
            kept = sanitize_look({"preset": "default", "custom": broken}).get("custom")
            resolved_palette("system", False, sanitize_look({"custom": broken}))
        except Exception as error:
            raise AssertionError(f"{broken!r} crashed with {error!r}") from None
        assert kept in (None, {"base": "light"})


def test_an_import_with_a_not_a_number_value_leaves_it_out_and_says_so() -> None:
    """Python's JSON reader accepts NaN, which no file format and no engine value allows. The wrapper
    rewrites it before the engine sees it, so the look keeps what it can and names the bad field."""
    got = import_look('{"kind": "FlexWeek look", "version": 1, "base": "poster", "corners": NaN}')
    assert got.look == {"base": "poster", "name": "My look"}
    assert len(got.problems) == 1 and "Corners" in got.problems[0]
