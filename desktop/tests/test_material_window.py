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

from PySide6.QtCore import QObject, QStandardPaths, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QDialog,
    QPushButton,
    QSpinBox,
    QWidget,
)

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.custom_look import save_look  # noqa: E402
from desktop.native.layouts.registry import sanitize_layout  # noqa: E402
from desktop.native.look import sanitize_look  # noqa: E402
from desktop.native.remind import reminder_lead_min  # noqa: E402
from desktop.native.version import VERSION  # noqa: E402
from desktop.native.weekmodel import clock_label  # noqa: E402
from desktop.native.window import WEEK_LIST_NAME, WINDOW_MIN_WIDTH, NativeWindow  # noqa: E402
from desktop.server import LocalServer  # noqa: E402
from desktop.tests.logic_support import past_setup  # noqa: E402
from desktop.tests.test_layouts_window import (  # noqa: E402
    PASSWORD,
    look_file,
    settled,
    wait_until,
)

SCHOOL_LIGHT = "#e4ebf7"
HOUR_ROW = 56
FALLBACK = "Material 3 could not open, so FlexWeek is showing the other styles. Your week is unchanged."
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
    """Put Material on screen. A refresh must not do this while Settings is open, so leave Settings first."""
    window._surface = "material"
    window._material_gave_up = False
    window._material_failed = ""
    if window._settings is not None and window._stack.currentWidget() is window._settings:
        window._close_settings(save=False)
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
        assert _qml(root, "navDay").property("visible") is True
        assert _qml(root, "navMonth").property("visible") is True
        assert _qml(root, "navMyDay").property("visible") is True
        assert _qml(root, "materialClock").property("text") == "7:00 PM"
        titles = _repeater_texts(root, "weekBlocks", "title")
        assert "School" in titles, titles
        assert "History essay" in titles, titles
        school = next(
            block
            for block in _named(root, "weekBlock")
            if any(str(label.property("text")) == "School" for label in _named(block, "title"))
        )
        assert int(school.property("y")) == 8 * HOUR_ROW
        shape = _named(school, "shape")[0]
        colour = shape.property("color")
        name = colour.name() if hasattr(colour, "name") else str(colour)
        assert name.lower() == SCHOOL_LIGHT.lower()
        assert int(shape.property("radius")) == 6
        title = _named(school, "title")[0]
        assert int(title.property("maximumLineCount")) == 2
        drawer = _qml(root, "homeworkDrawer")
        week = _qml(root, "materialWeek")
        assert int(drawer.property("width")) == 320
        assert int(drawer.property("x")) == int(week.property("width")) - 320
        start = date.fromisoformat(session.week_start)
        assert f"Thu {(start + timedelta(days=3)).day}" in _repeater_texts(root, "dayHeaders", "dayHeader")
        assert _qml(root, "nowLine").property("visible") is True
        assert _qml(root, "homeworkCount").property("text") == "1"
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


def test_an_unsent_settings_change_survives_the_swap(qapp: QApplication, window: NativeWindow) -> None:
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
        if window._settings is not None and window._stack.currentWidget() is page:
            window._surface = "widgets"
            window._material_gave_up = False
            window._close_settings(save=False)


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
        assert window.toast.isVisible()
        assert window.toast.text() == FALLBACK
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


def _menu_labels(menu: QWidget) -> list[str]:
    labels: list[str] = []
    for action in menu.actions():
        if action.isSeparator() or not action.isVisible():
            continue
        labels.append(action.text().split("\t", 1)[0])
        inner = action.menu()
        if inner is not None:
            labels.extend(_menu_labels(inner))
    return labels


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
    _pump(qapp)


def test_an_unsent_reminder_lead_survives_the_swap_back(qapp: QApplication, window: NativeWindow) -> None:
    """A refused preference save must still be on the lead control after Material and after reopening."""
    window._surface = "widgets"
    window._material_gave_up = False
    window._on_week()
    window._open_settings()
    page = window._settings
    assert page is not None
    lead = page.findChild(QSpinBox, "prefLead")
    assert lead.value() == 5
    assert lead.value() == reminder_lead_min(window.session.preferences)
    saved: list[object] = []

    def refuse(wanted: dict, _done: object) -> bool:
        saved.append(wanted.get("reminder_lead_min"))
        return False

    original = window.session.save_preferences
    window.session.save_preferences = refuse
    try:
        lead.setValue(17)
        for timer in page.findChildren(QTimer):
            timer.stop()
        page.findChild(QPushButton, "chooseMaterial").click()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "materialPage"
        window._use_widgets_styles()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert window._settings_unsent() is True
        assert lead.value() == 17
        assert window._save_before_leaving(lambda: None) is False
        QTest.qWait(200)
        assert 17 in saved
        window._open_settings()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "settingsPage"
        assert page.findChild(QSpinBox, "prefLead").value() == 17
    finally:
        leaving = window._leaving
        if leaving is not None:
            leaving.stop()
            leaving.deleteLater()
            window._leaving = None
        window.session.save_preferences = original
        lead.setValue(reminder_lead_min(window.session.preferences))
        for timer in page.findChildren(QTimer):
            timer.stop()
        if window._stack.currentWidget() is page:
            window._close_settings()
        window._surface = "widgets"
        window._material_gave_up = False


def test_a_missing_token_file_falls_back_and_leaves_no_material_page(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from desktop.native.material import theme

    _drop_material(window, qapp)
    theme._schemes.cache_clear()
    missing = tmp_path / "tokens.json"
    monkeypatch.setattr(theme, "tokens_path", lambda: missing)
    window._surface = "material"
    window._material_gave_up = False
    window.toast.hide()
    try:
        window._on_week()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert window.toast.isVisible()
        assert window.toast.text() == FALLBACK
        assert window._surface == "material"
        assert window.findChild(QWidget, "materialPage") is None
        broken = tmp_path / "broken.json"
        broken.write_text("{", encoding="utf-8")
        monkeypatch.setattr(theme, "tokens_path", lambda: broken)
        theme._schemes.cache_clear()
        window._material_gave_up = False
        window._material_failed = ""
        window.toast.hide()
        window._on_week()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert window.toast.text() == FALLBACK
        assert window.findChild(QWidget, "materialPage") is None
    finally:
        theme._schemes.cache_clear()
        _drop_material(window, qapp)
        window._material_gave_up = False
        window._material_failed = ""
        window._surface = "widgets"
        window._save_look()


def test_a_publish_failure_falls_back_to_the_widgets_week(qapp: QApplication, window: NativeWindow) -> None:
    window._surface = "widgets"
    window._material_gave_up = False
    window._material_failed = ""
    page = window._ensure_material()
    assert page is not None
    original = page.publish

    def boom() -> None:
        raise RuntimeError("publication failed")

    page.publish = boom
    window._surface = "material"
    window.toast.hide()
    try:
        window._on_week()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert window.toast.isVisible()
        assert window.toast.text() == FALLBACK
        assert window._surface == "material"
        assert [(block["id"], block["title"]) for block in window.session.blocks]
    finally:
        if window._material_page is page:
            page.publish = original
        window._material_gave_up = False
        window._material_failed = ""
        window._surface = "widgets"
        window._save_look()


def test_a_failed_material_is_not_tried_again_until_the_version_or_a_new_choice(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.toast.hide()
    window._surface = "material"
    window._material_failed = VERSION
    window._material_gave_up = False
    window._save_look()
    window._material_gave_up = False
    window._load_look()
    window._on_week()
    _pump(qapp)
    try:
        assert window._material_gave_up is True
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert window.toast.isHidden()
        assert json.loads(look_file().read_text())["surface"] == "material"
        stored = json.loads(look_file().read_text())
        stored["material_failed"] = "0.0.0"
        look_file().write_text(json.dumps(stored))
        window._load_look()
        assert window._material_gave_up is False
        window._on_week()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "materialPage"
        window._use_widgets_styles()
        _pump(qapp)
        assert "material_failed" not in json.loads(look_file().read_text())
        window._surface = "material"
        window._material_failed = VERSION
        window._material_gave_up = True
        window._save_look()
        window._open_settings()
        window._settings.findChild(QPushButton, "chooseMaterial").click()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "materialPage"
        assert "material_failed" not in json.loads(look_file().read_text())
    finally:
        window._material_gave_up = False
        window._material_failed = ""
        window._surface = "widgets"
        if window._settings is not None and window._stack.currentWidget() is window._settings:
            window._close_settings()
        window._save_look()


def test_focus_back_returns_to_material(qapp: QApplication, window: NativeWindow) -> None:
    """Focus is a screen inside Material now: the page stays Material's, and Back closes the screen."""
    root = _show_material(qapp, window)
    window._open_focus_screen()
    _pump(qapp)
    focus = window._material_page.bridge.focus
    try:
        assert window._stack.currentWidget().objectName() == "materialPage"
        assert focus.open
        assert _qml(root, "materialFocus").property("visible") is True
        focus.back()
        _pump(qapp)
        assert not focus.open
        assert window._stack.currentWidget().objectName() == "materialPage"
    finally:
        focus.hide()
        window._surface = "widgets"
        window._material_gave_up = False
        window._on_week()


def test_a_refresh_with_focus_open_keeps_focus_and_the_plan_prompt(
    qapp: QApplication, window: NativeWindow
) -> None:
    trace = {"placed": [], "kept": "focus"}
    window.session.trace = trace
    window.session._fresh_plan = True
    _show_material(qapp, window)
    window._open_focus_screen()
    window.session.week_changed.emit()
    _pump(qapp)
    focus = window._material_page.bridge.focus
    try:
        assert window._stack.currentWidget().objectName() == "materialPage"
        assert focus.open
        assert window.plan_review.isHidden()
        assert window.session._fresh_plan is True
        focus.back()
        _pump(qapp)
        assert not focus.open
        assert window.session.consume_plan_review() == trace
    finally:
        window.session.trace = None
        window.session._fresh_plan = False
        window.plan_review.hide()
        focus.hide()
        window._surface = "widgets"
        window._material_gave_up = False
        window._on_week()


def test_a_refresh_with_settings_open_keeps_settings(qapp: QApplication, window: NativeWindow) -> None:
    trace = {"placed": [], "kept": "settings"}
    window.session.trace = trace
    window.session._fresh_plan = True
    _show_material(qapp, window)
    window._open_settings()
    assert window._stack.currentWidget().objectName() == "settingsPage"
    window.session.week_changed.emit()
    _pump(qapp)
    try:
        assert window._stack.currentWidget().objectName() == "settingsPage"
        assert window.plan_review.isHidden()
        assert window.session._fresh_plan is True
    finally:
        window.session.trace = None
        window.session._fresh_plan = False
        window.plan_review.hide()
        if window._settings is not None and window._stack.currentWidget() is window._settings:
            window._surface = "widgets"
            window._close_settings()
        window._surface = "widgets"
        window._material_gave_up = False
        window._on_week()


def test_closing_settings_returns_to_material(qapp: QApplication, window: NativeWindow) -> None:
    _show_material(qapp, window)
    window._open_settings()
    window._settings.findChild(QPushButton, "settingsDone").click()
    _pump(qapp)
    try:
        assert window._stack.currentWidget().objectName() == "materialPage"
    finally:
        window._surface = "widgets"
        window._material_gave_up = False
        if window._settings is not None and window._stack.currentWidget() is window._settings:
            window._close_settings()
        window._on_week()


def test_the_material_clock_and_now_line_advance(qapp: QApplication, window: NativeWindow) -> None:
    root = _show_material(qapp, window)
    original = window.session.now_ms
    thursday = datetime.fromisoformat(window.session.week_start) + timedelta(days=3, hours=19)
    later = thursday + timedelta(hours=1)
    window.session.now_ms = lambda: int(later.timestamp() * 1000)
    try:
        window._layout_tick.timeout.emit()
        _pump(qapp)
        assert _qml(root, "materialClock").property("text") == clock_label(20 * 60)
        assert int(_qml(root, "nowLine").property("y")) == 20 * HOUR_ROW
    finally:
        window.session.now_ms = original
        if window._material_page is not None and window._stack.currentWidget() is window._material_page:
            window._material_page.bridge.refresh()
        window._use_widgets_styles()


def test_material_more_lists_the_planning_actions_and_leaves_the_widgets_menu_alone(
    qapp: QApplication, window: NativeWindow
) -> None:
    _show_material(qapp, window)
    bridge = window._material_page.bridge
    bridge.openMore()
    _pump(qapp)
    try:
        assert QApplication.activePopupWidget() is None
        assert bridge.sheets.moreOpen is True
        labels = [row["label"] for row in bridge.sheets.moreEntries if row["id"]]
        assert labels == [
            "Running late",
            "Unfinished",
            "Week as a list",
            "Routines",
            "Quick focus",
            "Replan all my homework",
            "Save this week now",
            "Help",
            "About FlexWeek",
            "Sign out",
        ]
        bridge.sheets.closeMore()
        window._use_widgets_styles()
        _pump(qapp)
        window.more_menu.popup(window.more_button.mapToGlobal(window.more_button.rect().bottomLeft()))
        _pump(qapp)
        assert "Unfinished" in _menu_labels(window.more_menu)
        assert WEEK_LIST_NAME in _menu_labels(window.more_menu)
    finally:
        window.more_menu.close()
        window._surface = "widgets"
        window._material_gave_up = False
        window._on_week()


def test_the_add_button_opens_homework_from_the_keyboard(qapp: QApplication, window: NativeWindow) -> None:
    root = _show_material(qapp, window)
    fab = _qml(root, "materialFab")
    assert "Rectangle" not in fab.metaObject().className()
    assert fab.property("activeFocusOnTab") is True
    sheets = window._material_page.bridge.sheets
    try:
        window.activateWindow()
        quick = window._material_page._quick
        quick.setFocus()
        fab.forceActiveFocus()
        _pump(qapp)
        QTest.keyClick(quick, Qt.Key.Key_Space)
        _pump(qapp)
        if sheets.kind != "homework":
            QTest.keyClick(quick, Qt.Key.Key_Return)
            _pump(qapp)
        assert sheets.kind == "homework"
        assert _named(root, "sheetTitle")[0].property("text") == "Add homework"
        assert QApplication.activeModalWidget() is None
        QTest.keyClick(quick, Qt.Key.Key_Escape)
        _pump(qapp)
        assert sheets.kind == ""
        assert quick.quickWindow().activeFocusItem() is fab
    finally:
        sheets.forceClose()
        window._use_widgets_styles()


def test_the_material_week_comes_from_the_session(qapp: QApplication, window: NativeWindow) -> None:
    root = _show_material(qapp, window)
    assert _named(root, "weekBlock")

    class Empty:
        occurrences: tuple = ()

    window.session.built_week = lambda: Empty()
    try:
        window._material_page.bridge.refresh()
        _pump(qapp)
        assert _named(root, "weekBlock") == []
    finally:
        del window.session.built_week
        window._material_page.bridge.refresh()
        window._use_widgets_styles()


def _accept_sign_out() -> None:
    """Press Sign out on the sheet that is about to open. Esc and Cancel leave the account signed in."""

    def press() -> None:
        sheet = QApplication.activeModalWidget()
        if sheet is not None and hasattr(sheet, "buttons"):
            sheet.buttons["yes"].click()

    QTimer.singleShot(200, press)


def test_sign_out_keeps_an_unsent_settings_change_on_both_surfaces(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A refused preference save is still the lead after Sign out is confirmed.

    Material's More and the Widgets button both reach the same sign-out. Signing out
    used to drop the draft and leave the saved lead at 5.
    """
    window._surface = "widgets"
    window._material_gave_up = False
    window._on_week()
    window._open_settings()
    page = window._settings
    assert page is not None
    lead = page.findChild(QSpinBox, "prefLead")
    assert lead.value() == 5
    assert lead.value() == reminder_lead_min(window.session.preferences)
    offered: list[object] = []
    logged_out: list[int] = []

    def refuse(wanted: dict, _done: object) -> bool:
        offered.append(wanted.get("reminder_lead_min"))
        return False

    original_save = window.session.save_preferences
    original_logout = window.session.logout

    def watch_logout() -> None:
        logged_out.append(reminder_lead_min(window.session.preferences))
        original_logout()

    window.session.save_preferences = refuse
    window.session.logout = watch_logout
    try:
        lead.setValue(17)
        for timer in page.findChildren(QTimer):
            timer.stop()
        root = _show_material(qapp, window)
        assert window._settings_unsent() is True
        window._material_page.bridge.openMore()
        _pump(qapp)
        assert window._material_page.bridge.sheets.moreOpen is True
        _accept_sign_out()
        window._material_page.bridge.sheets.moreAction("signOut")
        QTest.qWait(700)
        assert logged_out == []
        assert window.session.account is not None
        assert reminder_lead_min(window.session.preferences) == 5
        assert lead.value() == 17
        assert 17 in offered
        assert window.session.message == (
            "Couldn't save, so FlexWeek stayed open. Your changes are still on screen. "
            "Choose Retry save, then sign out again."
        )
        assert root.objectName() == "materialShell"

        offered.clear()
        window._use_widgets_styles()
        _pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert window._settings_unsent() is True
        _accept_sign_out()
        window.findChild(QPushButton, "signOut").click()
        QTest.qWait(700)
        assert logged_out == []
        assert window.session.account is not None
        assert reminder_lead_min(window.session.preferences) == 5
        assert lead.value() == 17
        assert 17 in offered
        assert "sign out again." in window.session.message
    finally:
        leaving = window._leaving
        if leaving is not None:
            leaving.stop()
            leaving.deleteLater()
            window._leaving = None
        window.session.logout = original_logout
        window.session.save_preferences = original_save
        if window.session.account is not None and page.findChild(QSpinBox, "prefLead") is not None:
            lead.setValue(reminder_lead_min(window.session.preferences))
            for timer in page.findChildren(QTimer):
                timer.stop()
        current = QApplication.activePopupWidget()
        if current is not None:
            current.close()
        sheet = QApplication.activeModalWidget()
        if isinstance(sheet, QDialog):
            sheet.reject()
        if window._stack.currentWidget() is page:
            window._close_settings()
        window._surface = "widgets"
        window._material_gave_up = False
        if window.session.account is not None:
            window._on_week()


def test_setup_writes_material_beside_the_layout(window: NativeWindow) -> None:
    window._surface = "material"
    window._material_failed = ""
    window._material_gave_up = False
    answer = {
        "look": sanitize_look(window._look),
        "layout": sanitize_layout({"main": "classic", "day": "one", "options": {"one": {"daybar": "hide"}}}),
        "pack": "system",
    }
    window._setup_step_left(0, 1, answer)
    stored = json.loads(look_file().read_text())
    assert stored["surface"] == "material"
    assert stored["layout"]["main"] == "classic"
    assert stored["layout"]["options"]["one"]["daybar"] == "hide"
    assert "surface" not in stored["layout"]
    window._surface = "widgets"
    window._load_look()
    assert window._surface == "material"
    assert window._layout["options"]["one"]["daybar"] == "hide"
    window._surface = "widgets"
    window._save_look()


def test_number_keys_open_each_screen_and_escape_returns_focus(
    qapp: QApplication, window: NativeWindow
) -> None:
    """1–5 leave the week for Day, Month, My day, and Settings, and Esc focuses that destination."""
    root = _show_material(qapp, window)
    bridge = window._material_page.bridge
    quick = window._material_page._quick
    try:
        assert bridge.property("screen") == "week"
        root.forceActiveFocus()
        _pump(qapp)
        for key, screen, page_name, title in (
            (Qt.Key.Key_1, "day", "materialDay", "Day"),
            (Qt.Key.Key_3, "month", "materialMonth", "Month"),
            (Qt.Key.Key_4, "myday", "materialMyDay", "My day"),
            (Qt.Key.Key_5, "settings", "materialSettings", "Settings"),
            (Qt.Key.Key_2, "week", "materialWeek", None),
        ):
            QTest.keyClick(quick, key)
            _pump(qapp)
            assert bridge.property("screen") == screen
            page = _qml(root, page_name)
            assert page.property("visible") is True
            if title is not None:
                assert _named(page, "screenTitle")[0].property("text") == title
        assert _qml(root, "materialSettings").property("visible") is False
        bridge.showPage("settings")
        _pump(qapp)
        settings = _qml(root, "materialSettings")
        assert settings.property("visible") is True
        assert _named(settings, "useWidgets")[0].property("text") == "Widgets styles"
        QTest.keyClick(quick, Qt.Key.Key_Escape)
        _pump(qapp)
        assert _qml(root, "navSettings").property("activeFocus") is True
        bridge.showPage("nope")
        assert bridge.property("screen") == "settings"
        bridge.showPage("week")
        _pump(qapp)
        assert bridge.property("screen") == "week"
        assert _named(root, "weekBlock")
    finally:
        window._use_widgets_styles()


def test_a_narrow_shell_uses_the_bar_and_parks_the_add_button(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Under 768 the rail is gone, Month sits in the top bar, and Add is 16px in and 96px up."""
    root = _show_material(qapp, window)
    window.setMinimumWidth(360)
    window.resize(700, 800)
    _pump(qapp)
    try:
        assert int(root.property("width")) < 768
        assert root.findChild(QObject, "materialRail") is None
        assert _qml(root, "materialBar").property("visible") is True
        assert int(_qml(root, "materialBar").property("height")) == 80
        fab = _qml(root, "materialFab")
        parent = fab.parent()
        assert int(fab.property("width")) == 56
        assert int(fab.property("height")) == 56
        assert int(fab.property("x")) == int(parent.property("width")) - 16 - 56
        assert int(fab.property("y")) == int(parent.property("height")) - 96 - 56
        assert _qml(root, "navMonth").property("visible") is True
        assert _qml(root, "navDay").property("visible") is True
        week = _qml(root, "materialWeek")
        drawer = _qml(root, "homeworkDrawer")
        assert int(week.property("scrollClearance")) == 96
        assert int(drawer.property("width")) == int(week.property("width"))
        assert int(root.property("enterMs")) == 300
    finally:
        window.setMinimumWidth(WINDOW_MIN_WIDTH)
        window.resize(1280, 800)
        _pump(qapp)
        window._use_widgets_styles()


def test_reduce_motion_runs_the_page_change_in_no_time(qapp: QApplication, window: NativeWindow) -> None:
    root = _show_material(qapp, window)
    bridge = window._material_page.bridge
    original = window._motion
    try:
        assert bridge.property("reduceMotion") is False
        assert int(root.property("enterMs")) == 300
        window._motion = "off"
        window._material_page.publish()
        _pump(qapp)
        assert bridge.property("reduceMotion") is True
        assert int(root.property("enterMs")) == 0
    finally:
        window._motion = original
        if window._material_page is not None:
            window._material_page.publish()
        window._use_widgets_styles()


def test_the_open_shell_publishes_the_theme_object(qapp: QApplication, window: NativeWindow) -> None:
    """The shell's theme map is the Slate light scheme plus the ink aliases and the three flags."""
    _show_material(qapp, window)
    theme = window._material_page.bridge.property("theme")
    try:
        assert theme["primary"] == "#3d6fc4"
        assert theme["onSurface"] == "#0f172a"
        assert theme["inkSurface"] == "#0f172a"
        assert theme["inkMuted"] == "#475569"
        assert theme["inverseOnSurface"] == "#f0f0f7"
        assert theme["density"] == "comfortable"
        assert theme["reduceMotion"] is False
        assert theme["highContrast"] is False
    finally:
        window._use_widgets_styles()


def test_register_fonts_returns_the_three_inter_faces(qapp: QApplication) -> None:
    from PySide6.QtGui import QFontDatabase

    from desktop.native.material.theme import INTER, register_fonts

    ids = register_fonts()
    assert len(ids) == 3
    families: list[str] = []
    for ident in ids:
        assert ident >= 0
        families.extend(QFontDatabase.applicationFontFamilies(ident))
    assert INTER in families


def test_opening_material_registers_those_faces(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from desktop.native.material import host as host_mod

    seen: list[tuple[int, ...]] = []
    real = host_mod.register_fonts

    def wrapped() -> tuple[int, ...]:
        found = real()
        seen.append(found)
        return found

    monkeypatch.setattr(host_mod, "register_fonts", wrapped)
    page = window._ensure_material()
    assert page is not None
    page._ready = False
    try:
        _show_material(qapp, window)
        assert seen
        assert len(seen[-1]) == 3
        assert all(ident >= 0 for ident in seen[-1])
    finally:
        window._use_widgets_styles()


def _press_item(qapp: QApplication, window: NativeWindow, item: QObject) -> None:
    from PySide6.QtCore import QPoint, QPointF

    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    QTest.mouseClick(
        window._material_page._quick,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(int(centre.x()), int(centre.y())),
    )
    _pump(qapp)


def test_rings_follow_the_last_input_in_the_real_window(qapp: QApplication, window: NativeWindow) -> None:
    """B3a3 (FIX-SPEC PR 6): a sheet opened with the mouse puts focus on Title with no ring; Esc is a key,
    so the focus it hands back shows its ring, even on the rail item that was just clicked."""
    root = _show_material(qapp, window)
    sheets = window._material_page.bridge.sheets
    try:
        _press_item(qapp, window, _named(root, "materialFab")[0])
        def title_rings() -> list[QObject]:
            return [ring for title in _named(root, "homeworkTitle") for ring in _named(title, "focusRing")]

        def focused() -> list[QObject]:
            return [ring for ring in title_rings() if ring.property("target").property("activeFocus")]

        wait_until(qapp, lambda: bool(focused()))
        title_ring = focused()[0]
        assert title_ring.property("target").property("activeFocus") is True
        assert title_ring.property("shown") is False

        week = _named(root, "navWeek")[0]
        sheets.forceClose()
        _pump(qapp)
        _press_item(qapp, window, week)
        QTest.keyClick(window._material_page._quick, Qt.Key.Key_Escape)
        _pump(qapp)
        assert week.property("activeFocus") is True
        assert _named(week, "focusRing")[0].property("shown") is True
    finally:
        sheets.forceClose()
        _pump(qapp)


def test_a_disposed_bridge_stops_following_the_week(qapp: QApplication, window: NativeWindow) -> None:
    """C5: dispose() cuts the session signal the bridge joined, so a week change after the drop
    reaches the bridge's own follower no more. The window's own follower is out of the way, since
    the window answers a week change through the page's publish, which refreshes directly."""
    _show_material(qapp, window)
    bridge = window.findChild(QObject, "materialBridge")
    assert bridge is not None
    session = window.session
    reached: list[str] = []
    original = bridge.refresh
    bridge.refresh = lambda: reached.append("refresh")
    window.session.week_changed.disconnect(window._on_week)
    try:
        bridge.dispose()
        session.week_changed.emit()
        _pump(qapp)
        assert reached == []
    finally:
        bridge.refresh = original
        session.week_changed.connect(window._on_week)
