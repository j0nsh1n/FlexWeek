"""Material 3 in the real window: the swap, the week, and a failure that keeps the session.

The numbers and titles below are the account's data and the spec's colours, not a
reading of the QML file.
"""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Iterator
from datetime import date, datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QStandardPaths, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton, QWidget  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.custom_look import save_look  # noqa: E402
from desktop.native.layouts.registry import sanitize_layout  # noqa: E402
from desktop.native.look import sanitize_look  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.server import LocalServer  # noqa: E402
from desktop.tests.logic_support import past_setup  # noqa: E402
from desktop.tests.test_layouts_window import (  # noqa: E402
    PASSWORD,
    look_file,
    settled,
    wait_until,
)

SCHOOL_LIGHT = "#EAE6FA"
HOUR_ROW = 56
NIGHT = {
    "name": "Night study",
    "base": "paper",
    "accent": "sea",
    "colours": {"page": "#1e2430", "card": "#262d3b", "text": "#e8ecf2", "line": "#394255"},
    "categories": {"class": {"hue": 140}},
    "corners": 4,
    "heading_font": "mono",
    "text_scale": 1.2,
}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-material-window"])
    yield application


@pytest.fixture(scope="module")
def window(qapp: QApplication, tmp_path_factory: pytest.TempPathFactory) -> Iterator[NativeWindow]:
    """Signed in, clock held at Thursday 19:00, School on weekday mornings and a History essay."""
    look_file().unlink(missing_ok=True)
    server = LocalServer(tmp_path_factory.mktemp("material") / "flexweek.db")
    server.start()
    made = NativeWindow(server.origin)
    made.show()
    made.resize(1280, 800)
    try:
        made.username.setText("material_student")
        made.password.setText(PASSWORD)
        made.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "recoveryPage")
        made.recovery_ack.setChecked(True)
        made.recovery_continue.click()
        past_setup(qapp, made)
        wait_until(qapp, lambda: made.session.preferences is not None)
        session = made.session
        thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=19)
        session.now_ms = lambda: int(thursday.timestamp() * 1000)
        session.add_block(
            {
                "id": "school",
                "title": "School",
                "kind": "locked",
                "category": "class",
                "start": "08:00",
                "duration_min": 390,
                "days": [0, 1, 2, 3, 4],
            }
        )
        session.add_homework(
            {
                "id": "essay",
                "title": "History essay",
                "due": sunday_due(session.week_start),
                "estimate_min": 60,
                "revision": 0,
            }
        )
        session.save()
        settled(qapp, made)
        work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
        work.update({"start": "18:45", "days": [3], "duration_min": 60})
        session.add_block(work)
        session.save()
        settled(qapp, made)
        yield made
    finally:
        with contextlib.suppress(RuntimeError):
            made.session.client.reset()
        made.hide()
        qapp.processEvents()
        server.stop()
        look_file().unlink(missing_ok=True)


def _pump(qapp: QApplication, count: int = 30) -> None:
    for _ in range(count):
        qapp.processEvents()


def _show_material(qapp: QApplication, window: NativeWindow) -> QObject:
    window._surface = "material"
    window._material_gave_up = False
    window.resize(1280, 800)
    window._on_week()
    _pump(qapp)
    quick = window._material_page._quick
    quick.grabFramebuffer()
    _pump(qapp)
    assert window._stack.currentWidget().objectName() == "materialPage"
    root = window._material_page.root
    assert root is not None
    return root


def _qml(root: QObject, name: str) -> QObject:
    found = root.findChild(QObject, name)
    assert found is not None, name
    return found


def _visuals(item: QObject) -> list[QObject]:
    """Every painted QML child.

    Repeater.itemAt returns None through PySide, and findChildren misses the rows:
    a delegate's QObject parent is the repeater model, while its visual parent is the grid.
    """
    found: list[QObject] = []
    if not hasattr(item, "childItems"):
        return found
    for child in item.childItems():
        found.append(child)
        found.extend(_visuals(child))
    return found


def _named(root: QObject, name: str) -> list[QObject]:
    return [item for item in _visuals(root) if str(item.objectName()) == name]


def _repeater_texts(root: QObject, repeater_name: str, label_name: str) -> list[str]:
    assert root.findChild(QObject, repeater_name) is not None, repeater_name
    return [str(item.property("text")) for item in _named(root, label_name)]


def test_material_sits_with_the_designs_and_a_design_leaves_it(qapp: QApplication) -> None:
    from desktop.native.settings import SettingsPage

    page = SettingsPage(None, {}, {}, {}, None)
    page.resize(900, 700)
    page.show()
    _pump(qapp)
    names = [
        "Today's app",
        "Timeline",
        "Mission control",
        "Bento",
        "Retro desktop",
        "Clay deck",
    ]
    main = page.findChild(QWidget, "layoutMain")
    assert [main.itemText(index) for index in range(main.count())] == names
    button = page.findChild(QPushButton, "chooseMaterial")
    assert button is not None and button.text() == "Material 3"
    section = page.layout_sections[0]
    assert section.surface() == "widgets"
    assert section.chosen() == "classic"
    heard: list[str] = []
    section.changed.connect(lambda: heard.append("changed"))
    section.show_surface("material")
    assert heard == []
    assert button.isChecked() is True
    assert section.surface() == "material"
    assert section.chosen() == "classic"
    look = page.findChild(QWidget, "layoutMain-look")
    assert look.isVisible() is False
    section.pick.cards[section.pick.currentIndex()].chosen.emit()
    _pump(qapp)
    assert section.surface() == "widgets"
    assert heard == ["changed"]
    look = page.findChild(QWidget, "layoutMain-look")
    assert look.isVisible() is True
    section.show_surface("material")
    timeline = next(card for card in section.pick.cards if card.accessibleName() == "Timeline")
    timeline.chosen.emit()
    assert section.chosen() == "timeline"
    assert section.surface() == "widgets"
    assert page.layout_sections[1].surface() == "widgets"
    page.hide()


def test_choosing_material_shows_the_week_and_swapping_back_keeps_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    session.add_homework(
        {
            "id": "worksheet",
            "title": "Math worksheet",
            "due": sunday_due(session.week_start),
            "estimate_min": 30,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    preferences = dict(session.preferences or {})
    preferences["clock_24h"] = False
    session.preferences = preferences
    block_ids = [block["id"] for block in session.blocks]

    for _ in range(3):
        root = _show_material(qapp, window)
        assert int(_qml(root, "materialRail").property("width")) == 80
        assert int(_qml(root, "materialFab").property("width")) == 56
        assert int(_qml(root, "materialFab").property("height")) == 56
        assert _qml(root, "navDay").property("visible") is False
        assert _qml(root, "navMonth").property("visible") is False
        assert _qml(root, "navMyDay").property("visible") is False
        assert _qml(root, "materialClock").property("text") == "7:00 PM"
        titles = _repeater_texts(root, "weekBlocks", "weekBlockTitle")
        assert "School" in titles, titles
        assert "History essay" in titles, titles
        school = next(
            block
            for block in _named(root, "weekBlock")
            if any(str(label.property("text")) == "School" for label in _named(block, "weekBlockTitle"))
        )
        assert int(school.property("y")) == 8 * HOUR_ROW
        colour = school.property("color")
        name = colour.name() if hasattr(colour, "name") else str(colour)
        assert name.lower() == SCHOOL_LIGHT.lower()
        assert int(school.property("radius")) == 12
        title = _named(school, "weekBlockTitle")[0]
        assert int(title.property("maximumLineCount")) == 2
        start = date.fromisoformat(session.week_start)
        assert f"Thu {(start + timedelta(days=3)).day}" in _repeater_texts(root, "dayHeaders", "dayHeader")
        assert _qml(root, "nowLine").property("visible") is True
        assert _qml(root, "homeworkCount").property("text") == "1 still needs a time"
        assert "Math worksheet" in _repeater_texts(root, "homeworkRows", "homeworkTitle")
        window._use_widgets_styles()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert window._surface == "widgets"
        assert [block["id"] for block in session.blocks] == block_ids

    preferences["clock_24h"] = True
    session.preferences = preferences
    root = _show_material(qapp, window)
    assert _qml(root, "materialClock").property("text") == "19:00"
    window._use_widgets_styles()


def test_an_unsent_settings_change_survives_the_swap(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._surface = "widgets"
    window._material_gave_up = False
    window._on_week()
    window._open_settings()
    page = window._settings
    assert page is not None
    clock = page.findChild(QWidget, "prefClock")
    # The change is whatever the open page is showing, not the account dict. A week refresh can
    # have built this page before a later test wrote the account's clock.
    wanted = not bool(clock.currentData())

    def refuse(_wanted: dict, _done: object) -> bool:
        return False

    original = window.session.save_preferences
    window.session.save_preferences = refuse
    try:
        clock.setCurrentIndex(0 if wanted else 1)
        for timer in page.findChildren(QTimer):
            timer.stop()
        page.findChild(QPushButton, "chooseMaterial").click()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "materialPage"
        assert page.updates()["clock_24h"] is wanted
        assert window._settings_unsent() is True
        window._use_widgets_styles()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert window._settings is page
        assert page.updates()["clock_24h"] is wanted
        window._open_settings()
        assert window._settings_unsent() is True
        assert bool(page.findChild(QWidget, "prefClock").currentData()) is wanted
    finally:
        window.session.save_preferences = original
        for timer in page.findChildren(QTimer):
            timer.stop()


def test_a_refresh_stays_on_material_and_does_not_take_the_plan_prompt(
    qapp: QApplication, window: NativeWindow
) -> None:
    trace = {"placed": [], "kept": "once"}
    window.session.trace = trace
    window.session._fresh_plan = True
    root = _show_material(qapp, window)
    assert root.objectName() == "materialShell"
    window.session.week_changed.emit()
    _pump(qapp)
    assert window._stack.currentWidget().objectName() == "materialPage"
    assert window.session.consume_plan_review() == trace
    window.session.trace = trace
    window.session._fresh_plan = True
    window._use_widgets_styles()
    _pump(qapp)
    assert window._stack.currentWidget().objectName() == "weekPage"
    assert window.session.consume_plan_review() is None


def test_a_load_or_graphics_failure_keeps_the_session_and_the_choice(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._surface = "material"
    window._material_gave_up = False
    window._save_look()
    before = [(block["id"], block["title"]) for block in window.session.blocks]
    told = window.session.message
    page = window._ensure_material()
    assert page is not None
    page.break_load = True
    try:
        window._on_week()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert [(block["id"], block["title"]) for block in window.session.blocks] == before
        assert json.loads(look_file().read_text())["surface"] == "material"
        assert window._surface == "material"
        assert window.session.message not in ("", told)
        window._on_week()
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert [(block["id"], block["title"]) for block in window.session.blocks] == before

        window._material_gave_up = False
        page.break_load = False
        page._on_scene_graph_error(None, "device lost")
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert [(block["id"], block["title"]) for block in window.session.blocks] == before
        assert json.loads(look_file().read_text())["surface"] == "material"
        assert window._surface == "material"
    finally:
        page.break_load = False
        window._material_gave_up = False
        window._surface = "widgets"


def test_saved_looks_round_trip_with_surface(window: NativeWindow) -> None:
    from desktop.native.custom_look import wear

    window._look = wear(sanitize_look(None), NIGHT)
    window._saved_looks = save_look([], NIGHT, "Night study")
    window._layout = sanitize_layout(
        {"main": "classic", "day": "one", "options": {"one": {"daybar": "hide"}}}
    )
    window._surface = "material"
    window._save_look()
    stored = json.loads(look_file().read_text())
    assert stored["surface"] == "material"
    assert "surface" not in stored["layout"]
    assert stored["layout"]["options"]["one"]["daybar"] == "hide"
    assert stored["saved_looks"] == [NIGHT]
    assert stored["custom"] == NIGHT

    aged = {key: value for key, value in stored.items() if key != "surface"}
    look_file().write_text(json.dumps(aged))
    window._load_look()
    assert window._surface == "widgets"
    assert window._saved_looks == [NIGHT]
    assert window._layout["options"]["one"]["daybar"] == "hide"
    assert window._look["custom"] == NIGHT

    aged["surface"] = "nope"
    look_file().write_text(json.dumps(aged))
    window._load_look()
    assert window._surface == "widgets"
    assert window._saved_looks == [NIGHT]

    aged["layout"]["surface"] = "material"
    aged["surface"] = "material"
    look_file().write_text(json.dumps(aged))
    window._load_look()
    assert window._surface == "material"
    assert "surface" not in window._layout
    assert window._saved_looks == [NIGHT]
    assert window._layout["options"]["one"]["daybar"] == "hide"
