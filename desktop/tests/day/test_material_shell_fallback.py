# ruff: noqa: F811
"""When Material 3 cannot draw with the graphics card, FlexWeek saves that this version must draw on the CPU
and starts a new copy that does. A failure while already drawing on the CPU shows a plain error page with
Quit and Try again. No path shows the Widgets week.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

from desktop.native import cpu_drawing
from desktop.native import window as window_module  # noqa: E402
from desktop.native.version import VERSION  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import (  # noqa: E402, F401
    material_window,
    qapp,
)
from desktop.tests.material_support import material_showing, page_showing, page_widget, pump  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import look_file  # noqa: E402


def _drop_material(window: NativeWindow, qapp: QApplication) -> None:
    """Remove the Material page, including one whose constructor died before it was stored."""
    doomed: list[QWidget] = []
    page = window._material_page
    window._material_page = None
    if page is not None:
        doomed.append(page)
    doomed.extend(window.findChildren(QWidget, "materialPage"))
    seen: set[int] = set()
    for item in doomed:
        if id(item) in seen:
            continue
        seen.add(id(item))
        if window._stack.indexOf(item) >= 0:
            window._stack.removeWidget(item)
        item.setParent(None)
        item.deleteLater()
    for bridge in window.findChildren(QObject, "materialBridge"):
        dispose = getattr(bridge, "dispose", None)
        if callable(dispose):
            dispose()
        bridge.setParent(None)
        bridge.deleteLater()
    pump(qapp)


def _blocks(window: NativeWindow) -> list[tuple[str, str]]:
    return [(block["id"], block["title"]) for block in window.session.blocks]


@pytest.fixture
def launches(monkeypatch: pytest.MonkeyPatch, material_window: NativeWindow) -> list[bool]:
    """Every request for a new copy, as its `cpu` flag. Nothing is really started or quit."""
    calls: list[bool] = []
    monkeypatch.setattr(cpu_drawing, "start_new_copy", lambda *, cpu: calls.append(cpu))
    monkeypatch.setattr(material_window, "_quit_now", lambda: None)
    return calls


def _on_graphics_card(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(cpu_drawing.BACKEND_ENV, raising=False)


def _on_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(cpu_drawing.BACKEND_ENV, cpu_drawing.SOFTWARE)


def _saved() -> dict:
    return json.loads(look_file().read_text())


def _week_page_never_shown(window: NativeWindow) -> None:
    assert page_showing(window) != "weekPage"


def test_a_load_failure_on_the_graphics_card_saves_the_cpu_key_and_asks_for_a_cpu_copy(
    qapp: QApplication,
    material_window: NativeWindow,
    launches: list[bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _on_graphics_card(monkeypatch)
    window = material_window
    window._surface = "material"
    window._material_gave_up = False
    window._save_look()
    before = _blocks(window)
    page = window._ensure_material()
    assert page is not None
    page.break_load = True

    window._on_week()
    pump(qapp)

    assert launches == [True]
    assert _saved()[cpu_drawing.LOOK_KEY] == VERSION
    assert _saved()["surface"] == "material"
    assert _blocks(window) == before
    _week_page_never_shown(window)


def test_a_graphics_error_on_the_graphics_card_asks_for_one_cpu_copy_however_often_it_is_reported(
    qapp: QApplication,
    material_window: NativeWindow,
    launches: list[bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _on_graphics_card(monkeypatch)
    window = material_window
    window._surface = "material"
    window._material_gave_up = False
    page = window._ensure_material()
    assert page is not None
    window._on_week()
    pump(qapp)

    page._on_scene_graph_error(None, "device lost")
    page._on_scene_graph_error(None, "device lost again")
    pump(qapp)

    assert launches == [True]
    assert _saved()[cpu_drawing.LOOK_KEY] == VERSION
    _week_page_never_shown(window)


def test_a_missing_or_broken_token_file_asks_for_a_cpu_copy_and_leaves_no_material_page(
    qapp: QApplication,
    material_window: NativeWindow,
    launches: list[bool],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from desktop.native.material import theme

    _on_graphics_card(monkeypatch)
    window = material_window
    _drop_material(window, qapp)
    theme._schemes.cache_clear()
    monkeypatch.setattr(theme, "tokens_path", lambda: tmp_path / "tokens.json")
    window._surface = "material"
    window._material_gave_up = False
    try:
        window._on_week()
        pump(qapp)
        assert launches == [True]
        assert window.findChild(QWidget, "materialPage") is None
        # The week page was already the window's page before Material was tried. It is the stand-in
        # until the CPU copy starts, not a switch to the Widgets week, which the on-CPU test covers.
    finally:
        # The scheme cache is shared by the whole run, so it must not keep the broken file's answer.
        theme._schemes.cache_clear()
        _drop_material(window, qapp)


def test_a_publish_failure_on_the_graphics_card_asks_for_a_cpu_copy(
    qapp: QApplication,
    material_window: NativeWindow,
    launches: list[bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _on_graphics_card(monkeypatch)
    window = material_window
    window._surface = "widgets"
    window._material_gave_up = False
    page = window._ensure_material()
    assert page is not None

    def boom() -> None:
        raise RuntimeError("publication failed")

    page.publish = boom
    window._surface = "material"

    window._on_week()
    pump(qapp)

    assert launches == [True]
    assert _saved()[cpu_drawing.LOOK_KEY] == VERSION
    assert window._surface == "material"
    _week_page_never_shown(window)


def test_start_up_draws_on_the_cpu_only_for_the_version_that_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "flexweek-look.json"
    monkeypatch.delenv(cpu_drawing.BACKEND_ENV, raising=False)

    path.write_text(json.dumps({cpu_drawing.LOOK_KEY: "0.0.0"}))
    assert cpu_drawing.apply_saved(path, VERSION) is False
    assert cpu_drawing.BACKEND_ENV not in os.environ

    path.write_text(json.dumps({cpu_drawing.LOOK_KEY: VERSION}))
    assert cpu_drawing.apply_saved(path, VERSION) is True
    assert os.environ[cpu_drawing.BACKEND_ENV] == cpu_drawing.SOFTWARE

    monkeypatch.delenv(cpu_drawing.BACKEND_ENV)
    assert cpu_drawing.apply_saved(tmp_path / "missing.json", VERSION) is False
    path.write_text("{")
    assert cpu_drawing.apply_saved(path, VERSION) is False
    assert cpu_drawing.BACKEND_ENV not in os.environ


def test_main_applies_the_saved_cpu_choice_before_the_window_is_made() -> None:
    source = (Path(__file__).parents[2] / "main.py").read_text()
    assert source.index("apply_saved_cpu_drawing(") < source.index("NativeWindow(origin")


def test_the_saved_key_does_not_stop_material_from_being_tried_and_is_kept_by_a_look_save(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _on_cpu(monkeypatch)
    window = material_window
    window._surface = "material"
    window._cpu_drawing_version = VERSION
    window._save_look()
    window._load_look()
    assert window._cpu_drawing_version == VERSION
    assert window._material_gave_up is False
    window._on_week()
    pump(qapp)
    assert material_showing(window)
    assert _saved()[cpu_drawing.LOOK_KEY] == VERSION

    # An older version's key is read, kept, and does not match this version at start-up.
    stored = _saved()
    stored[cpu_drawing.LOOK_KEY] = "0.0.0"
    look_file().write_text(json.dumps(stored))
    window._load_look()
    assert window._cpu_drawing_version == "0.0.0"
    assert window._cpu_drawing_version != VERSION


def test_after_the_cpu_copy_starts_the_snackbar_says_so_once(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _on_cpu(monkeypatch)
    monkeypatch.setenv(cpu_drawing.NOTICE_ENV, "1")
    window = material_window
    window._surface = "material"
    window._material_gave_up = False
    window._on_week()
    pump(qapp)
    assert material_showing(window)
    assert window.session.message == cpu_drawing.NOTICE
    assert cpu_drawing.NOTICE_ENV not in os.environ
    window.session.message = ""
    window._on_week()
    pump(qapp)
    assert window.session.message == ""


def test_a_failure_while_drawing_on_the_cpu_shows_the_error_page_and_try_again_clears_the_key(
    qapp: QApplication,
    material_window: NativeWindow,
    launches: list[bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _on_cpu(monkeypatch)
    window = material_window
    window._surface = "material"
    window._material_gave_up = False
    window._cpu_drawing_version = VERSION
    window._save_look()
    before = _blocks(window)
    page = window._ensure_material()
    assert page is not None
    page.break_load = True

    window._on_week()
    pump(qapp)

    shown = page_widget(window)
    assert shown.objectName() == "drawErrorPage"
    assert launches == []
    assert VERSION in shown.findChild(QLabel, "drawErrorVersion").text()
    assert shown.findChild(QLabel, "drawErrorLine").text() == cpu_drawing.DRAW_ERROR
    assert shown.findChild(QPushButton, "drawErrorQuit").text() == "Quit"
    assert _blocks(window) == before
    # Later refreshes keep the error page up, never the week.
    window._on_week()
    pump(qapp)
    assert page_showing(window) == "drawErrorPage"

    shown.findChild(QPushButton, "drawErrorRetry").click()
    pump(qapp)
    assert launches == [False]
    assert cpu_drawing.LOOK_KEY not in _saved()
    assert _saved()["surface"] == "material"


def test_no_failure_path_shows_the_widgets_week(
    qapp: QApplication,
    material_window: NativeWindow,
    launches: list[bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = material_window
    window._surface = "material"
    for on_cpu in (False, True):
        window._material_gave_up = False
        window._relaunching = False
        (_on_cpu if on_cpu else _on_graphics_card)(monkeypatch)
        page = window._ensure_material()
        assert page is not None
        page.break_load = True
        window._on_week()
        pump(qapp)
        _week_page_never_shown(window)
        page.break_load = False


def test_an_update_found_on_the_draw_error_page_is_offered_and_installed_there(
    qapp: QApplication,
    material_window: NativeWindow,
    launches: list[bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Material cannot be drawn at all, so there is no update sheet; an update may be the fix, so the error
    page offers it (Jonathan, 2026-11-19) with the same download and install as the sheet."""
    _on_cpu(monkeypatch)
    window = material_window
    window._surface = "material"
    window._material_gave_up = False
    window._cpu_drawing_version = VERSION
    page = window._ensure_material()
    assert page is not None
    page.break_load = True
    window._on_week()
    pump(qapp)
    shown = page_widget(window)
    assert shown.objectName() == "drawErrorPage"
    line = shown.findChild(QLabel, "drawErrorUpdateLine")
    install = shown.findChild(QPushButton, "drawErrorInstall")
    assert not line.isVisibleTo(shown) and not install.isVisibleTo(shown), "no update was found yet"

    asked: list[dict] = []
    monkeypatch.setattr(window._updater, "download", asked.append)
    monkeypatch.setattr(window, "_save_look", lambda: None)
    window._updates = {}
    update = {"version": "9.9.9", "notes": ""}
    window._on_update_found(update)
    pump(qapp)
    assert line.isVisibleTo(shown) and line.text() == "FlexWeek 9.9.9 is ready"
    assert install.isVisibleTo(shown) and install.text() == "Update now"

    install.click()
    pump(qapp)
    assert asked == [update]
    assert line.text() == "Downloading…"
    assert not install.isEnabled()
    window._on_update_progress(50, 200)
    assert line.text() == "Downloading… 25%"
    window._on_update_problem("Could not download the update.")
    assert line.text() == "Could not download the update."
    assert install.isEnabled(), "after a problem the student can try again"

    install.click()
    quits: list[bool] = []
    monkeypatch.setattr(window, "quit_app", lambda: quits.append(True))
    monkeypatch.setattr(window_module, "apply_update", lambda _path: "The update could not be put in place.")
    window._on_update_ready("/downloaded/flexweek")
    assert line.text() == "The update could not be put in place. Open the release page to update by hand."
    assert install.isEnabled() and quits == []

    install.click()
    monkeypatch.setattr(window_module, "apply_update", lambda _path: None)
    window._on_update_ready("/downloaded/flexweek")
    assert line.text() == "Update installed. FlexWeek will close so the new version can start."
    wait_until(qapp, lambda: quits == [True], 5)
    assert shown.findChild(QLabel, "drawErrorLine").text() == cpu_drawing.DRAW_ERROR
