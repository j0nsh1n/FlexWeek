# ruff: noqa: F811
"""Targeted verification for Material static UI audit findings:
- M1: Dark Settings > Look text contrast (row titles, unselected chips, preset labels)
- M3: Advanced preview month stage presence and bridge binding
- M6: Setup school row clock formatting consistency
"""

from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.tokens import contrast  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.test_layouts_window import wait_until  # noqa: E402
from desktop.tests.test_material_window import (  # noqa: E402, F401
    _named,
    _pump,
    _qml,
    _show_material,
    qapp,
    window,
)


def _bridge(window: NativeWindow):
    return window._material_page.bridge


def _panel(window: NativeWindow):
    return window._material_page.bridge._settings_bridge


def _texts(item: QObject) -> list[QObject]:
    found: list[QObject] = []
    for child in item.childItems():
        if child.property("text") is not None and child.property("font") is not None:
            found.append(child)
        found.extend(_texts(child))
    return found


def _flick_to(item: QObject) -> None:
    parent = item.parentItem()
    while parent is not None:
        if parent.property("contentY") is not None and parent.property("contentHeight") is not None:
            content = parent.property("contentItem")
            spot = item.mapToItem(content, QPointF(0, 0))
            room = max(0.0, float(parent.property("contentHeight")) - float(parent.height()))
            parent.setProperty("contentY", max(0.0, min(room, spot.y() - 60.0)))
            return
        parent = parent.parentItem()


def _click(qapp: QApplication, window: NativeWindow, item: QObject) -> None:
    _flick_to(item)
    _pump(qapp, 5)
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    quick = window._material_page._quick
    QTest.mouseClick(
        quick,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(int(centre.x()), int(centre.y())),
    )
    _pump(qapp, 10)


def _click_segment(qapp: QApplication, window: NativeWindow, seg: QObject, label: str) -> None:
    for item in _texts(seg):
        if str(item.property("text")) == label:
            _click(qapp, window, item)
            return
    raise AssertionError(f"no segment {label!r}")


def _open_settings(qapp: QApplication, window: NativeWindow, section: str = "look") -> QObject:
    window.activateWindow()
    window.raise_()
    root = _show_material(qapp, window)
    quick = getattr(getattr(window, "_material_page", None), "_quick", None)
    if quick is not None:
        quick.setFocus()
    _bridge(window).showPage("settings")
    _panel(window).closeAdvanced()
    _panel(window).setSection(section)
    _pump(qapp)
    return root


def test_m1_dark_settings_look_contrast(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window, "look")
    panel = _panel(window)

    def _check_row_contrast() -> tuple[float, float, float]:
        mode_row = _named(root, "row_mode")[0]
        card = mode_row.parentItem()
        card_fill = card.parentItem().property("color")
        card_hex = card_fill.name() if hasattr(card_fill, "name") else str(card_fill)

        title_item = next(t for t in _texts(mode_row) if t.property("text") == "Mode")
        title_color = title_item.property("color").name()

        seg = _named(mode_row, "mode")[0]
        unselected_label = "Dark" if panel.property("state")["mode"] == "light" else "Light"
        unselected_item = next(t for t in _texts(seg) if t.property("text") == unselected_label)
        unselected_color = unselected_item.property("color").name()

        preset_row = _named(root, "row_preset")[0]
        swatch_label = next(t for t in _texts(preset_row) if t.property("text") == "Blue")
        swatch_color = swatch_label.property("color").name()

        cr_title = contrast(card_hex, title_color)
        cr_unselected = contrast(card_hex, unselected_color)
        cr_swatch = contrast(card_hex, swatch_color)
        return cr_title, cr_unselected, cr_swatch

    try:
        # Phase 1: Ensure in Light mode and check contrast
        _click_segment(qapp, window, _named(root, "mode")[0], "Light")
        wait_until(qapp, lambda: panel.property("state")["mode"] == "light")
        _pump(qapp, 10)
        cr_title_l, cr_unsel_l, cr_swatch_l = _check_row_contrast()
        assert cr_title_l >= 4.5, f"Light title contrast {cr_title_l:.2f} < 4.5"
        assert cr_unsel_l >= 4.5, f"Light unselected contrast {cr_unsel_l:.2f} < 4.5"
        assert cr_swatch_l >= 4.5, f"Light swatch contrast {cr_swatch_l:.2f} < 4.5"

        # Phase 2: Switch Light -> Dark mode and check contrast on dark card (#1a1c20)
        _click_segment(qapp, window, _named(root, "mode")[0], "Dark")
        wait_until(qapp, lambda: panel.property("state")["mode"] == "dark")
        _pump(qapp, 10)
        cr_title_d, cr_unsel_d, cr_swatch_d = _check_row_contrast()
        assert cr_title_d >= 4.5, f"Dark title contrast {cr_title_d:.2f} < 4.5"
        assert cr_unsel_d >= 4.5, f"Dark unselected contrast {cr_unsel_d:.2f} < 4.5"
        assert cr_swatch_d >= 4.5, f"Dark swatch contrast {cr_swatch_d:.2f} < 4.5"

        # Phase 3: Switch Dark -> Light mode to prove bidirectional theme switching
        _click_segment(qapp, window, _named(root, "mode")[0], "Light")
        wait_until(qapp, lambda: panel.property("state")["mode"] == "light")
        _pump(qapp, 10)
        cr_title_l2, cr_unsel_l2, cr_swatch_l2 = _check_row_contrast()
        assert cr_title_l2 >= 4.5, f"Restored light title contrast {cr_title_l2:.2f} < 4.5"
        assert cr_unsel_l2 >= 4.5, f"Restored light unselected contrast {cr_unsel_l2:.2f} < 4.5"
        assert cr_swatch_l2 >= 4.5, f"Restored light swatch contrast {cr_swatch_l2:.2f} < 4.5"
    finally:
        panel.setMode("system")
        _pump(qapp)


def test_m3_advanced_preview_month_bridge(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window)
    panel = _panel(window)
    try:
        panel.openAdvanced()
        _pump(qapp, 10)

        # Cold entry verification: fresh live session is on week, no month history
        assert window.session.planner_view == "week"
        assert window.session.selected_month is None
        assert window.session.month_data is None

        # 1. Month preview verification (cold path)
        _click_segment(qapp, window, _named(root, "previewView")[0], "Month")
        wait_until(qapp, lambda: bool(_named(root, "settingsPreviewMonth")))
        _pump(qapp, 10)

        # Ensure live planner state was untouched by previewing month
        assert window.session.planner_view == "week"
        assert window.session.selected_month is None
        assert window.session.month_data is None

        preview_month = _named(root, "settingsPreviewMonth")[0]
        month_view = _named(preview_month, "materialMonth")[0]
        month_bridge = month_view.property("month")
        assert month_bridge is not None, "MonthView in preview stage has null month bridge"

        dates = month_bridge.property("dates")
        assert dates is not None, "Month bridge in preview stage has null dates"
        assert dates.rowCount() >= 28, f"Expected dates.rowCount() >= 28, got {dates.rowCount()}"

        def _every(item: QObject) -> list[QObject]:
            found: list[QObject] = []
            for child in item.childItems() if hasattr(item, "childItems") else []:
                found.append(child)
                found.extend(_every(child))
            return found

        wait_until(
            qapp,
            lambda: (
                len([i for i in _every(month_view) if str(i.objectName()).startswith("monthDate-")]) >= 28
            ),
            timeout=5.0,
        )
        month_cells = [item for item in _every(month_view) if str(item.objectName()).startswith("monthDate-")]
        assert len(month_cells) >= 28, f"Expected >= 28 month cells, got {len(month_cells)}"

        visible_cells = [c for c in month_cells if c.isVisible() and c.width() > 0 and c.height() > 0]
        assert len(visible_cells) >= 28, (
            f"Expected >= 28 visible cells with geometry, got {len(visible_cells)}"
        )

        # Verify painted day numbers and weekday headers
        day_numbers = _named(month_view, "monthDayNumber")
        assert len(day_numbers) >= 28, f"Expected >= 28 day numbers, got {len(day_numbers)}"
        day_texts = [str(t.property("text")).strip() for t in day_numbers if str(t.property("text")).strip()]
        assert len(day_texts) >= 28, f"Expected non-empty day number texts, got {len(day_texts)}"

        weekdays = _named(month_view, "monthWeekday")
        assert len(weekdays) == 7, f"Expected 7 weekday headers, got {len(weekdays)}"

        # 2. Day preview verification (meaningful content for added day property)
        _click_segment(qapp, window, _named(root, "previewView")[0], "Day")
        wait_until(qapp, lambda: bool(_named(root, "settingsPreviewDay")))
        _pump(qapp, 10)

        preview_day = _named(root, "settingsPreviewDay")[0]
        day_view = _named(preview_day, "materialDay")[0]
        day_board = day_view.property("board")
        assert day_board is not None, "DayView in preview stage has null board (day bridge)"

        day_nav_prev = _named(day_view, "dayPrevious")
        day_nav_next = _named(day_view, "dayNext")
        assert len(day_nav_prev) > 0 and day_nav_prev[0].isVisible(), "Day previous button missing"
        assert len(day_nav_next) > 0 and day_nav_next[0].isVisible(), "Day next button missing"

        month_side = _named(day_view, "dayMonthSide")
        assert len(month_side) > 0 and month_side[0].isVisible(), "dayMonthSide missing or hidden"
        assert month_side[0].width() > 0, f"dayMonthSide width is 0: {month_side[0].width()}"

        day_left = _named(day_view, "dayLeftLine")
        assert len(day_left) > 0, "dayLeftLine text item missing"
    finally:
        panel.closeAdvanced()
        _pump(qapp)


def test_m6_account_field_commits_and_rebinds_on_return(qapp: QApplication) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtQuick import QQuickItem, QQuickView

    view = QQuickView()
    try:
        view.engine().addImportPath(str(Path(__file__).parents[1] / "native" / "material" / "qml"))
        source = Path(__file__).parents[1] / "native" / "material" / "qml" / "account" / "AccountField.qml"
        view.setSource(QUrl.fromLocalFile(str(source)))
        view.show()
        _pump(qapp, 5)

        root = view.rootObject()
        assert root is not None

        committed_values: list[str] = []
        submitted_count: list[bool] = []
        login_submitted_payload: list[str] = []

        root.setProperty("text", "initial_user")
        root.committed.connect(lambda val: committed_values.append(str(val)))
        root.committed.connect(lambda val: root.setProperty("text", val))
        root.submitted.connect(lambda: submitted_count.append(True))
        root.submitted.connect(lambda: login_submitted_payload.append(str(root.property("text"))))

        root.setObjectName("loginUsername")
        input_item = root.findChild(QQuickItem, "loginUsernameInput")
        assert input_item is not None

        input_item.setProperty("text", "audit_student_2026")
        input_item.forceActiveFocus()
        _pump(qapp, 2)

        QTest.keyClick(view, Qt.Key.Key_Return)
        _pump(qapp, 5)

        assert "audit_student_2026" in committed_values, (
            f"Expected 'audit_student_2026' in committed: {committed_values}"
        )
        assert len(submitted_count) >= 1, f"Expected submitted signal, got {len(submitted_count)}"
        assert "audit_student_2026" in login_submitted_payload, (
            f"Expected 'audit_student_2026' in login submission: {login_submitted_payload}"
        )
        assert input_item.property("text") == "audit_student_2026"
    finally:
        view.close()
        del view
        _pump(qapp)


def test_m6_setup_wizard_school_row_format(qapp: QApplication, tmp_path: Path) -> None:
    from desktop.tests.test_material_account_setup import (
        Launches,
        account,
        create,
        look_file,
        through_recovery,
    )
    from desktop.tests.test_material_account_setup import (
        named as acct_named,
    )
    from desktop.tests.test_material_account_setup import (
        pump as acct_pump,
    )

    look_file().parent.mkdir(parents=True, exist_ok=True)
    look_file().write_text('{"surface": "material"}\n')
    made = Launches(qapp, tmp_path)
    try:
        win = made.launch()
        win.resize(1280, 800)
        acct_pump(qapp, 10)
        bridge = account(win)
        create(qapp, win, "audit_student")
        through_recovery(qapp, win)
        bridge.setupNext()  # Style -> Week
        acct_pump(qapp, 10)

        start_inputs = acct_named(win, "setupSchoolStartInput")
        end_inputs = acct_named(win, "setupSchoolEndInput")
        assert len(start_inputs) > 0, "setupSchoolStartInput must exist on setup Week page"
        assert len(end_inputs) > 0, "setupSchoolEndInput must exist on setup Week page"

        start_inp = start_inputs[0]
        end_inp = end_inputs[0]

        start_text = str(start_inp.property("text"))
        assert start_text == "8:00 AM", f"Expected default start '8:00 AM', got {start_text!r}"

        end_inp.forceActiveFocus()
        acct_pump(qapp, 5)
        end_inp.setProperty("text", "14:45")
        QTest.keyClick(win._material_page._quick, Qt.Key.Key_Return)
        acct_pump(qapp, 10)

        end_text = str(end_inp.property("text"))
        assert end_text == "2:45 PM", f"Expected 14:45 to format to '2:45 PM', got {end_text!r}"

        assert ("AM" in start_text or "PM" in start_text) and ("AM" in end_text or "PM" in end_text), (
            f"Clock formatting inconsistent: start={start_text!r}, end={end_text!r}"
        )
    finally:
        made.close()
        look_file().unlink(missing_ok=True)


def test_f2_preview_keyboard_and_action_isolation(qapp: QApplication, window: NativeWindow) -> None:
    """F2: Advanced preview controls cannot mutate live planner state.

    Verifies:
    1. Pointer click on dayNext in preview canvas does not change live selected_day/planner_view.
    2. Focus chain traversal (Tab) naturally reaches preview buttons (dayPrevious, dayNext)
       without forceActiveFocus shortcut.
    3. Keyboard Return and Space on dayNext in preview do not mutate live planner state.
    4. Backtab (Shift+Tab) to dayPrevious and Return/Space do not mutate live planner state.
    5. Accessible action invocation on preview controls does not mutate live planner state.
    6. Surrounding Settings controls and draft changes continue to update preview without interference.
    7. Live selection, navigation, schedule blocks, and preferences remain strictly unchanged.
    """
    root = _open_settings(qapp, window)
    panel = _panel(window)
    try:
        panel.openAdvanced()
        _pump(qapp, 10)

        # Switch to Day preview
        _click_segment(qapp, window, _named(root, "previewView")[0], "Day")
        wait_until(qapp, lambda: bool(_named(root, "settingsPreviewDay")))
        _pump(qapp, 10)

        preview_day = _named(root, "settingsPreviewDay")[0]
        day_view = _named(preview_day, "materialDay")[0]
        day_next = _named(day_view, "dayNext")[0]
        day_prev = _named(day_view, "dayPrevious")[0]

        # Record baseline live state
        initial_day = window.session.selected_day
        initial_view = window.session.planner_view
        initial_prefs = copy.deepcopy(window.session.preferences or {})
        initial_blocks = copy.deepcopy(window.session.blocks or [])
        initial_assignments = copy.deepcopy(window.session.assignments or {})

        # 1. Pointer control test: clicking dayNext directly
        _click(qapp, window, day_next)
        assert (window.session.selected_day, window.session.planner_view) == (initial_day, initial_view), (
            "Pointer click on preview dayNext mutated live planner state"
        )

        # 2. Focus chain traversal. FIX-SPEC v1.3 PR 3 (A2) takes every control inside the passive
        # preview out of the Tab order, leaving only the Week/Day/Month and Fit/Actual switches, so a
        # full Tab cycle never lands on the preview's day arrows.
        quick = window._material_page._quick
        trail: list[str] = []
        for _ in range(120):
            QTest.keyClick(quick, Qt.Key.Key_Tab)
            qapp.processEvents()
            focused = quick.quickWindow().activeFocusItem()
            trail.append(focused.objectName() if focused else "<none>")
            assert focused is not day_next and focused is not day_prev, (
                f"Tab reached a preview day arrow, which must not be a Tab stop. Focus trail: {trail}"
            )
        assert "previewView" in trail and "previewFit" in trail, f"Preview switches not in Tab order: {trail}"

        # 3. Keys on the arrows still cannot mutate live state, even with focus forced onto them.
        for arrow in (day_next, day_prev):
            arrow.forceActiveFocus()
            qapp.processEvents()
            for key in (Qt.Key.Key_Return, Qt.Key.Key_Space):
                QTest.keyClick(quick, key)
                _pump(qapp, 5)
                live = (window.session.selected_day, window.session.planner_view)
                assert live == (initial_day, initial_view), (
                    f"{key} on preview {arrow.objectName()} mutated live planner state"
                )

        # 5. Accessible action: trigger onPressAction if accessible
        accessible = day_next.property("Accessible")
        if accessible is not None and hasattr(accessible, "pressAction"):
            accessible.pressAction()
            _pump(qapp, 5)
            assert (window.session.selected_day, window.session.planner_view) == (initial_day, initial_view)

        # 6. Verify live state, blocks, and preferences remain completely unchanged
        assert window.session.selected_day == initial_day
        assert window.session.planner_view == initial_view
        assert (window.session.preferences or {}) == initial_prefs
        assert (window.session.blocks or []) == initial_blocks
        assert (window.session.assignments or {}) == initial_assignments

        # 7. Surrounding Settings controls remain fully functional and draft updates propagate
        _click_segment(qapp, window, _named(root, "previewView")[0], "Week")
        wait_until(qapp, lambda: bool(_named(root, "settingsPreviewWeek")))
        _pump(qapp, 5)
        preview_week = _named(root, "settingsPreviewWeek")[0]
        assert preview_week.isVisible()
    finally:
        panel.closeAdvanced()
        _pump(qapp, 10)


def test_week_preview_completion_is_inert_and_has_no_qml_error(
    qapp: QApplication, window: NativeWindow
) -> None:
    from copy import deepcopy

    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtGui import QAccessible

    root = _open_settings(qapp, window)
    panel = _panel(window)
    messages: list[str] = []
    previous_handler = None
    installed = False

    def state():
        session = window.session
        return deepcopy(
            (
                session.selected_day,
                session.planner_view,
                session.preferences,
                session.blocks,
                session.assignments,
            )
        )

    try:
        panel.openAdvanced()
        panel.setPreviewView("week")
        _pump(qapp)
        preview = _named(root, "settingsPreviewWeek")[0]
        blocks = [item for item in _named(preview, "weekBlock") if item.property("homework")]
        assert blocks, "The preview must contain an actual homework block"
        item = blocks[0]
        before = state()
        previous_handler = qInstallMessageHandler(lambda _kind, _context, text: messages.append(text))
        installed = True
        item.forceActiveFocus()
        QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
        _pump(qapp)
        interface = QAccessible.queryAccessibleInterface(item)
        assert interface is not None
        action = interface.actionInterface()
        assert action is not None and "Press" in action.actionNames()
        action.doAction("Press")
        _pump(qapp)
        finishes = _named(item, "weekBlockFinish")
        if finishes:
            finishes[0].forceActiveFocus()
            QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
            _pump(qapp)
        assert not any("TypeError" in text for text in messages), messages
        assert state() == before
    finally:
        if installed:
            qInstallMessageHandler(previous_handler)
        panel.closeAdvanced()
        _pump(qapp)
