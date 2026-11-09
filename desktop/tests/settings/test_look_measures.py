"""The measures of a look (radius, scale, sizes) are worked out once per look and then found again,
and a different look never gets another's."""

from __future__ import annotations

import pytest

import desktop.native.look as look_module
from desktop.native.look import look_measures
from desktop.native.tokens import TEXT_SCALE
from desktop.tests.settings.support_look import look_of


def test_look_measures_memoises_sanitize_look_per_look(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeated look_measures for one look must not re-sanitize; a different look gets fresh measures."""
    real = look_module.sanitize_look
    calls = 0

    def counting(raw: object) -> dict:
        nonlocal calls
        calls += 1
        return real(raw)

    monkeypatch.setattr(look_module, "sanitize_look", counting)
    look_module._LOOK_MEASURES_CACHE.clear()
    look = look_of("default", text="normal")
    other = look_of("default", text="large")
    for _ in range(100):
        look_measures(look)
    assert calls == 1
    normal_scale = look_measures(look)["scale"]
    large = look_measures(other)
    assert calls == 2
    assert large["scale"] != normal_scale


def test_look_measures_is_found_by_the_look_object_without_building_its_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The window draws with one look dict for as long as the look stays; the measures are asked for on
    every paint, so asking again with that same dict must not walk it into a key again."""
    look = look_of("default", text="large")
    first = look_measures(look)
    keys = 0
    real = look_module._look_json_key

    def counting(raw: object) -> str:
        nonlocal keys
        keys += 1
        return real(raw)

    monkeypatch.setattr(look_module, "_look_json_key", counting)
    for _ in range(50):
        assert look_measures(look) is first
    assert keys == 0


def test_an_edited_look_gives_fresh_measures_and_the_same_look_the_cached_ones() -> None:
    """The window replaces its look dict when the look changes, so a new dict with a new text size must
    be measured again, even though the old one is still cached."""
    normal = look_of("default", text="normal")
    large = look_of("default", text="large")
    assert look_measures(large)["scale"] > look_measures(normal)["scale"]
    edited = {**normal, "knobs": {**normal["knobs"], "text": "large"}}
    assert edited is not normal
    assert look_measures(edited)["scale"] == look_measures(large)["scale"]
    assert look_measures(normal) is look_measures(normal)
    assert look_measures(edited) is not look_measures(normal)


def test_look_measures_cannot_be_written_to() -> None:
    measures = look_measures(look_of("default"))
    with pytest.raises(TypeError):
        measures["radius"] = 99  # type: ignore[index]
    assert look_measures(look_of("default"))["radius"] != 99


def test_a_look_dict_freed_after_use_never_hands_its_measures_to_a_later_dict() -> None:
    """The cache is keyed by the look object's identity. Python reuses the identity of a dict that is
    gone, so the cache holds on to the dicts it has seen: a later, different look cannot land on it."""
    texts = ("normal", "normal", "large", "large", "small", "normal", "large", "small")
    for round_ in range(300):
        text = texts[round_ % len(texts)]
        look = look_of("default", text=text)
        assert look_measures(look)["scale"] == TEXT_SCALE[text]
        del look
