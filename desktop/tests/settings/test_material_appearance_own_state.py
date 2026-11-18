"""Material's light or dark and its contrast come from Material's own saved choice and the device, never from
the Widgets look or the account's theme pack."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from desktop.native.material import host
from desktop.native.material.host import appearance_of
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import show_material
from desktop.tests.window_support import look_file, qapp  # noqa: F401

WIDGETS_KEYS = {
    "preset": "high-contrast",
    "knobs": {"text": "large"},
    "layout": "classic",
    "surface": "widgets",
    "saved_looks": [{"name": "Mine", "look": {"preset": "pastel"}}],
}


def device(monkeypatch: pytest.MonkeyPatch, dark: bool) -> None:
    monkeypatch.setattr(host, "device_is_dark", lambda: dark)


def store(material: dict | None, **widgets: object) -> None:
    look_file().parent.mkdir(parents=True, exist_ok=True)
    body: dict = dict(widgets)
    if material is not None:
        body["material"] = material
    look_file().write_text(json.dumps(body) + "\n", encoding="utf-8")


def widgets_dark_and_high(window: NativeWindow) -> None:
    """The Widgets side says dark and High contrast; none of it may reach Material."""
    window.session.preferences = {**(window.session.preferences or {}), "theme_pack": "nocturne"}
    window._look = {**window._look, "preset": "high-contrast"}


@pytest.mark.parametrize("device_dark", [True, False])
def test_system_follows_the_device_whatever_the_widgets_look_says(
    qapp, window, monkeypatch, device_dark
) -> None:
    store({"mode": "system", "contrast": "standard"})
    widgets_dark_and_high(window)
    device(monkeypatch, device_dark)
    assert appearance_of(window) == ("dark" if device_dark else "light", "std")


def test_a_light_pack_does_not_turn_a_dark_device_light(qapp, window, monkeypatch) -> None:
    store({"mode": "system"})
    window.session.preferences = {**(window.session.preferences or {}), "theme_pack": "light-frost"}
    device(monkeypatch, True)
    assert appearance_of(window)[0] == "dark"


@pytest.mark.parametrize("device_dark", [True, False])
def test_material_light_and_dark_win_over_the_device(qapp, window, monkeypatch, device_dark) -> None:
    device(monkeypatch, device_dark)
    store({"mode": "light"})
    assert appearance_of(window)[0] == "light"
    store({"mode": "dark"})
    assert appearance_of(window)[0] == "dark"


def test_the_contrast_is_materials_own_choice(qapp, window, monkeypatch) -> None:
    device(monkeypatch, False)
    store({"contrast": "high"})
    assert appearance_of(window)[1] == "high"
    store({"contrast": "standard"}, preset="high-contrast")
    assert appearance_of(window)[1] == "std", "a Widgets High contrast preset is not Material's contrast"


def test_signed_out_follows_the_device_and_keeps_this_computers_contrast(qapp, window, monkeypatch) -> None:
    store({"mode": "dark", "contrast": "high"})
    monkeypatch.setattr(window, "_wears_carried_look", lambda: True)
    device(monkeypatch, False)
    assert appearance_of(window) == ("light", "high")
    device(monkeypatch, True)
    assert appearance_of(window) == ("dark", "high")
    store({"mode": "light", "contrast": "std"})
    assert appearance_of(window) == ("dark", "std")


def test_a_look_file_with_widgets_keys_opens_material_and_keeps_them(qapp, window, monkeypatch) -> None:
    store({"mode": "dark", "contrast": "high"}, **WIDGETS_KEYS)
    before = look_file().read_text(encoding="utf-8")
    device(monkeypatch, False)
    assert appearance_of(window) == ("dark", "high")
    show_material(qapp, window)
    window._material_page.bridge.reload_material()
    assert look_file().read_text(encoding="utf-8") == before
    kept = json.loads(before)
    assert {key: kept[key] for key in WIDGETS_KEYS} == WIDGETS_KEYS
