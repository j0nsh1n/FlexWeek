# ruff: noqa: F811
"""The packaged smoke test also opens Material 3, and fails when the Widgets fallback is what shows.

The smoke test also leaves the computer's saved style as it found it: the next smoke run on the same
data folder must not open straight into Material.

A release that installs but gives a Material 3 student the "could not open" fallback has to fail its
smoke test. The report keeps its `ok` and `stage` fields; `material_ok` says which half failed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop import main as app_main
from desktop.main import PAINTED_MIN_COLORS, SMOKE_PASSED, NativeSmoke, material_state
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import faded_in
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file, qapp  # noqa: F401


def pump(qapp: QApplication, count: int = 30) -> None:
    for _ in range(count):
        qapp.processEvents()


def last_stage_of_the_smoke(
    qapp: QApplication,
    window: NativeWindow,
    report: Path,
    monkeypatch: pytest.MonkeyPatch,
    before: str = "widgets",
) -> dict[str, object]:
    """Run the smoke test's own Material stage on the signed-in window and read its report."""
    monkeypatch.setattr(window, "quit_app", lambda: None)
    monkeypatch.setattr(app_main.QApplication, "exit", staticmethod(lambda _code=0: None))
    window.resize(1280, 800)
    window.show()
    pump(qapp)
    window._surface = before
    window._on_week()
    pump(qapp)
    smoke = NativeSmoke(window, report, True)
    smoke._poll.stop()
    smoke._facts_colors = 0
    window._back_to_material()
    smoke._stage = "material window"
    for _ in range(200):
        smoke._check()
        if report.exists():
            break
        pump(qapp, 5)
    wait_until(qapp, report.exists, what="the smoke report")
    return json.loads(report.read_text())


def test_the_smoke_passes_when_the_material_window_is_showing(
    qapp: QApplication, window: NativeWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    facts = last_stage_of_the_smoke(qapp, window, tmp_path / "smoke.json", monkeypatch)
    assert facts["ok"] is True
    assert facts["stage"] == SMOKE_PASSED
    assert facts["material_ok"] is True
    assert int(facts["material_painted_colors"]) >= PAINTED_MIN_COLORS  # type: ignore[call-overload]


def test_the_smoke_fails_when_material_fell_back_to_widgets(
    qapp: QApplication, window: NativeWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = window._ensure_material()
    assert page is not None
    page.break_load = True
    facts = last_stage_of_the_smoke(qapp, window, tmp_path / "smoke.json", monkeypatch)
    assert facts["ok"] is False
    assert facts["stage"] != SMOKE_PASSED
    assert "Material" in str(facts["stage"])
    assert facts["material_ok"] is False


def test_material_state_tells_the_window_from_the_fallback(qapp: QApplication, window: NativeWindow) -> None:
    window.resize(1280, 800)
    window.show()
    window._surface = "material"
    window._material_gave_up = False
    window._material_failed = ""
    window._on_week()
    pump(qapp)
    page = window._material_page
    assert page is not None and page.root is not None
    page._quick.grabFramebuffer()
    pump(qapp)
    faded_in(qapp, page.root)
    state, colors = material_state(window)
    assert state == "shown"
    assert colors >= PAINTED_MIN_COLORS
    window._give_up_material()
    assert material_state(window) == ("fallback", 0)


def saved_surface() -> object:
    return json.loads(look_file().read_text()).get("surface")


@pytest.mark.parametrize("break_load", [False, True])
def test_the_smoke_puts_the_widgets_style_back_before_it_quits(
    qapp: QApplication,
    window: NativeWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    break_load: bool,
) -> None:
    window._save_look()
    assert saved_surface() == "widgets"
    if break_load:
        page = window._ensure_material()
        assert page is not None
        page.break_load = True
    last_stage_of_the_smoke(qapp, window, tmp_path / "smoke.json", monkeypatch)
    assert saved_surface() == "widgets"
    assert window._surface == "widgets"
    assert window._stack.currentWidget().objectName() == "weekPage"


def test_the_smoke_leaves_a_material_computer_on_material(
    qapp: QApplication, window: NativeWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    facts = last_stage_of_the_smoke(qapp, window, tmp_path / "smoke.json", monkeypatch, before="material")
    assert facts["ok"] is True
    assert saved_surface() == "material"
    assert window._surface == "material"
