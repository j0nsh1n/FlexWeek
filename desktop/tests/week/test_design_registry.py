"""The layout choice a look file keeps: Today's app is the only design, and an older file that names a
design this build no longer has still loads as Today's app."""

from __future__ import annotations

from desktop.native.layout_choice import (
    DESIGN_LOOKS,
    LAYOUTS,
    sanitize_layout,
)

GONE = ("timeline", "bento", "retro")


def test_the_registry_holds_todays_app_and_no_day_screen() -> None:
    assert [spec.id for spec in LAYOUTS.values() if spec.role == "plan"] == ["classic"]
    assert [spec.id for spec in LAYOUTS.values() if spec.role == "day"] == []


def test_todays_app_offers_its_signature_high_contrast_dark_and_your_look() -> None:
    curated = DESIGN_LOOKS["classic"]
    option = next(option for option in LAYOUTS["classic"].options if option.key == "look")
    assert option.values == tuple(value for value, _label in curated) + ("your",)
    assert curated[0][0] not in {"preset:high-contrast", "pack:dark-frost"}
    assert ("preset:high-contrast", "High contrast") in curated
    assert any(value.startswith("pack:dark-") or value == "preset:terminal" for value, _ in curated)
    assert len(curated) >= 4


def test_options_are_known_and_defaults_are_shipped() -> None:
    for spec in LAYOUTS.values():
        assert {option.level for option in spec.options} <= {"style", "detail"}
        assert len({option.key for option in spec.options}) == len(spec.options)
        for option in spec.options:
            assert option.default in option.values
    assert next(option for option in LAYOUTS["classic"].options if option.key == "look").default == "your"


def test_missing_design_looks_keep_the_account_look() -> None:
    choice = sanitize_layout({"main": "classic", "options": {}})
    assert choice["options"] == {}
    for spec in LAYOUTS.values():
        assert next(option for option in spec.options if option.key == "look").default == "your"


def test_layout_sanitizer_drops_unknown_values_keys_and_non_dict_options() -> None:
    clean = sanitize_layout(
        {
            "main": "classic",
            "day": "dial",
            "options": {
                "classic": {"look": "preset:nope", "strange": "value"},
                "timeline": "not a dict",
                "ghost": {"look": "your"},
            },
        }
    )
    assert clean == {"main": "classic", "day": "dial", "options": {}}


def test_layout_sanitizer_keeps_a_valid_look_choice() -> None:
    kept = sanitize_layout({"main": "classic", "options": {"classic": {"look": "preset:paper"}}})
    assert kept == {"main": "classic", "day": "dial", "options": {"classic": {"look": "preset:paper"}}}


def test_a_look_file_that_names_a_removed_design_loads_as_todays_app() -> None:
    for design in GONE:
        loaded = sanitize_layout(
            {"main": design, "day": "dial", "options": {design: {"look": "your", "density": "compact"}}}
        )
        assert loaded == {"main": "classic", "day": "dial", "options": {}}, design


def test_bad_layouts_fall_back_and_wrong_roles_do_not_load() -> None:
    shipped = {"main": "classic", "day": "dial", "options": {}}
    for raw in (None, "bento", [], {"main": 7, "day": None, "options": "x"}):
        assert sanitize_layout(raw) == shipped
    assert sanitize_layout({"main": "one", "day": "bento"}) == shipped


def test_an_old_colour_choice_for_todays_app_becomes_your_look() -> None:
    migrated = sanitize_layout({"main": "classic", "options": {"classic": {"colour": "unknown"}}})
    assert migrated["options"]["classic"]["look"] == "your"
