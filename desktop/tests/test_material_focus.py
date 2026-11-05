"""Material's Focus screen and the two focus rules, against the real window and session.

Expected words and times are the app's and the spec's (a 30-minute default focus, a 15-minute break,
"Alerts muted", "Finish"), not read back from the QML file.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import contextlib
import itertools
from collections.abc import Iterator
from copy import deepcopy

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QObject, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.test_layouts_window import settled  # noqa: E402
from desktop.tests.test_material_window import (  # noqa: E402, F401
    _pump,
    _qml,
    _show_material,
    qapp,
    window,
)


@contextlib.contextmanager
def rules(window: NativeWindow, owned: bool = True, **prefs: object) -> Iterator[None]:
    """Material's focus rules on (or off) with these preferences, for one test."""
    session = window.session
    before = session.preferences
    before_owner = session.material_owns
    session.preferences = {**(before or {}), **prefs}
    session.material_owns = (lambda: True) if owned else None
    try:
        yield
    finally:
        session.reset_focus()
        session.preferences = before
        session.material_owns = before_owner


SLOT = itertools.count()


def next_slot() -> tuple[int, str]:
    """A free evening half hour on Monday to Friday, after School, so no two blocks share one."""
    index = next(SLOT)
    return index // 16, f"{16 + (index % 16) // 2}:{'30' if index % 2 else '00'}"


def homework(qapp: QApplication, window: NativeWindow, name: str, sessions: int) -> list[dict]:
    """A homework with `sessions` placed work blocks, each 30 minutes."""
    session = window.session
    session.add_homework(
        {
            "id": name,
            "title": name.title(),
            "due": sunday_due(session.week_start),
            "estimate_min": 30 * sessions,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    first = next(block for block in session.blocks if block.get("assignment_id") == name)
    day, start = next_slot()
    first.update({"start": start, "days": [day], "duration_min": 30})
    session.add_block(first)
    for index in range(1, sessions):
        extra = deepcopy(first)
        day, start = next_slot()
        extra.update({"id": f"{name}-{index}", "start": start, "days": [day]})
        session.add_block(extra)
    session.save()
    settled(qapp, window)
    return [block for block in session.blocks if block.get("assignment_id") == name]


def run_out(qapp: QApplication, window: NativeWindow) -> None:
    """The countdown reaches zero."""
    session = window.session
    session.focus["endsAt"] = session.now_ms() - 1
    session.tick_focus()
    settled(qapp, window)


def start(window: NativeWindow, block: dict) -> bool:
    return window.session.start_focus(block["id"], block["days"][0])


def block_named(window: NativeWindow, block_id: str) -> dict:
    return next(block for block in window.session.blocks if block["id"] == block_id)


def test_auto_complete_finishes_only_the_session_that_ran_and_leaves_the_homework_open(
    qapp: QApplication, window: NativeWindow
) -> None:
    blocks = homework(qapp, window, "lab", 2)
    first, second = blocks
    with rules(window, focus_auto_complete=True):
        assert start(window, first)
        run_out(qapp, window)
        done = block_named(window, first["id"])
        assert done["completed"] is True and done["completed_day"] == first["days"][0]
        assert not block_named(window, second["id"]).get("completed")
        assert not window.session.assignments["lab"].get("completed")


def test_auto_complete_finishes_the_homework_too_when_that_was_its_last_session(
    qapp: QApplication, window: NativeWindow
) -> None:
    only = homework(qapp, window, "poem", 1)[0]
    with rules(window, focus_auto_complete=True):
        assert start(window, only)
        run_out(qapp, window)
        assert block_named(window, only["id"])["completed"] is True
        assert window.session.assignments["poem"]["completed"] is True


def test_the_last_of_two_sessions_finishes_the_homework_after_the_first_left_it_open(
    qapp: QApplication, window: NativeWindow
) -> None:
    first, second = homework(qapp, window, "maps", 2)
    with rules(window, focus_auto_complete=True):
        assert start(window, first)
        run_out(qapp, window)
        assert not window.session.assignments["maps"].get("completed")
        window.session.reset_focus()
        assert start(window, second)
        run_out(qapp, window)
        assert block_named(window, second["id"])["completed"] is True
        assert window.session.assignments["maps"]["completed"] is True


@pytest.mark.parametrize(
    ("owned", "prefs"),
    [
        (True, {}),  # the setting is off by default
        (True, {"focus_auto_complete": False}),
        (False, {"focus_auto_complete": True}),  # a Widgets style never finishes a block by itself
    ],
)
def test_nothing_is_finished_unless_the_rule_is_on_in_material(
    qapp: QApplication, window: NativeWindow, owned: bool, prefs: dict
) -> None:
    name = f"quiet{int(owned)}{len(prefs)}{prefs.get('focus_auto_complete', 'x')}"
    only = homework(qapp, window, name, 1)[0]
    with rules(window, owned, **prefs):
        assert start(window, only)
        run_out(qapp, window)
        assert not block_named(window, only["id"]).get("completed")
        assert not window.session.assignments[name].get("completed")


def test_a_quick_focus_has_no_block_to_finish_and_does_not_fail(
    qapp: QApplication, window: NativeWindow
) -> None:
    with rules(window, focus_auto_complete=True):
        assert window.session.start_quick_focus()
        run_out(qapp, window)
        assert window.session.focus is not None  # on to its break, as before


def test_skip_does_not_auto_complete_the_block(
    qapp: QApplication, window: NativeWindow
) -> None:
    only = homework(qapp, window, "skipme", 1)[0]
    with rules(window, focus_auto_complete=True):
        assert start(window, only)
        window.session.advance_focus(False)
        settled(qapp, window)
        assert window.session.focus["phase"] == "break"
        assert not block_named(window, only["id"]).get("completed")
        assert not window.session.assignments["skipme"].get("completed")


REMINDER = {"title": "Soccer", "body": "Starts in 5 minutes", "kind": "reminder"}
FOCUS_NOTICE = {"title": "Break", "body": "History essay", "kind": "focus", "tone": "soft"}


WORDS = "Soccer — Starts in 5 minutes"  # how the window words a reminder when it does show it


@pytest.fixture()
def toasted(window: NativeWindow) -> Iterator[list[str]]:
    """The reminder words the window really put on screen, after the session's holding back."""
    seen: list[str] = []
    original = window._say_in_toast

    def spy(words: str, *args: object, **kwargs: object) -> None:
        seen.append(words)
        original(words, *args, **kwargs)  # type: ignore[arg-type]

    window._say_in_toast = spy  # type: ignore[method-assign]
    yield seen
    del window._say_in_toast


def test_reminders_wait_during_a_focus_work_phase_and_come_when_it_ends(
    qapp: QApplication, window: NativeWindow, toasted: list[str]
) -> None:
    session = window.session
    with rules(window):
        assert session.hold_alerts([REMINDER]) == [REMINDER]  # no focus: nothing is held
        assert session.start_quick_focus()
        assert session.focus_mutes_alerts()
        assert session.hold_alerts([FOCUS_NOTICE]) == [FOCUS_NOTICE]  # the timer's own still pass
        session.alerts.emit([REMINDER])
        assert toasted == []  # still working: the reminder is held back
        session.toggle_focus_pause()
        assert session.focus_mutes_alerts()  # paused is still inside focus
        assert toasted == []
        session.advance_focus(False)  # Skip to the break
        assert session.focus["phase"] == "break"
        assert not session.focus_mutes_alerts()
        assert toasted.count(WORDS) == 1  # reminder shown once the work phase was over
        assert session.release_held_alerts() == []  # and only once


@pytest.mark.parametrize(
    ("owned", "prefs"),
    [(True, {"focus_auto_mute": False}), (False, {})],
)
def test_nothing_is_held_when_the_rule_is_off_or_a_widgets_style_is_in_use(
    qapp: QApplication, window: NativeWindow, owned: bool, prefs: dict
) -> None:
    with rules(window, owned, **prefs):
        assert window.session.start_quick_focus()
        assert not window.session.focus_mutes_alerts()
        assert window.session.hold_alerts([REMINDER]) == [REMINDER]


def test_a_reminder_that_arrives_during_focus_is_not_shown_until_focus_ends(
    qapp: QApplication, window: NativeWindow, toasted: list[str]
) -> None:
    with rules(window):
        assert window.session.start_quick_focus()
        window.session.alerts.emit([REMINDER])
        assert toasted == []
        window.session.reset_focus()  # Finish
        assert toasted == [WORDS]


def test_a_reminder_shows_at_once_when_the_rule_is_off(
    qapp: QApplication, window: NativeWindow, toasted: list[str]
) -> None:
    with rules(window, focus_auto_mute=False):
        assert window.session.start_quick_focus()
        window.session.alerts.emit([REMINDER])
        assert toasted == [WORDS]


def open_focus(qapp: QApplication, window: NativeWindow) -> tuple[QObject, QObject]:
    root = _show_material(qapp, window)
    window._open_focus_screen()
    _pump(qapp)
    return root, window._material_page.bridge.focus


def close_focus(window: NativeWindow, focus: QObject) -> None:
    window.session.reset_focus()
    focus.hide()
    window._surface = "widgets"
    window._material_gave_up = False
    window._on_week()


def text_of(root: QObject, name: str) -> str:
    return str(_qml(root, name).property("text"))


def test_the_screen_opens_ready_and_start_runs_the_sessions_own_30_minute_timer(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, focus = open_focus(qapp, window)
    try:
        assert focus.open and window._stack.currentWidget().objectName() == "materialPage"
        assert text_of(root, "focusPhase") == "Ready when you are"
        assert text_of(root, "focusTitle") == "Quick focus"
        assert text_of(root, "focusTime") == "30:00"
        assert _qml(root, "focusStart").property("visible") is True
        assert _qml(root, "focusPause").property("visible") is False
        focus.begin()
        _pump(qapp)
        assert window.session.focus is not None  # the Widgets focus strip reads the same timer
        assert window.session.focus["phase"] == "work"
        assert text_of(root, "focusPhase") == "Focus"
        assert text_of(root, "focusTime") in ("30:00", "29:59")
        assert _qml(root, "focusStart").property("visible") is False
        for name in ("focusSkip", "focusPause", "focusFinish"):
            assert _qml(root, name).property("visible") is True
    finally:
        close_focus(window, focus)


def test_the_screen_uses_the_presets_25_and_5_when_the_session_has_them(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, focus = open_focus(qapp, window)
    session = window.session
    before = session.preferences
    session.preferences = {**before, "timer_work_min": 25, "timer_break_min": 5}
    try:
        _pump(qapp)
        focus.refresh()
        assert focus.timeText == "25:00"
        focus.begin()
        assert focus.timeText in ("25:00", "24:59")
        focus.skip()
        _pump(qapp)
        assert focus.phaseText == "Break"
        assert focus.timeText in ("05:00", "04:59")
    finally:
        session.preferences = before
        close_focus(window, focus)


def test_pause_resume_and_skip_drive_the_session_and_say_so(qapp: QApplication, window: NativeWindow) -> None:
    root, focus = open_focus(qapp, window)
    try:
        focus.begin()
        assert text_of(root, "focusPause") == "Pause"
        focus.togglePause()
        _pump(qapp)
        assert window.session.focus["running"] is False
        assert text_of(root, "focusPhase") == "Focus · Paused"
        assert text_of(root, "focusPause") == "Resume"
        focus.togglePause()
        assert window.session.focus["running"] is True
        focus.skip()
        _pump(qapp)
        assert window.session.focus["phase"] == "break"
        assert text_of(root, "focusPhase") == "Break"
        focus.skip()
        assert window.session.focus["phase"] == "work"
    finally:
        close_focus(window, focus)


def test_pause_and_resume_keep_the_buttons_still(qapp: QApplication, window: NativeWindow) -> None:
    root, focus = open_focus(qapp, window)
    try:
        focus.begin()
        _pump(qapp)
        pause, skip, finish = _qml(root, "focusPause"), _qml(root, "focusSkip"), _qml(root, "focusFinish")
        before = (float(pause.x()), float(pause.width()), float(skip.x()), float(finish.x()))
        focus.togglePause()
        _pump(qapp)
        assert text_of(root, "focusPause") == "Resume"
        assert (float(pause.x()), float(pause.width()), float(skip.x()), float(finish.x())) == before
        focus.togglePause()
        _pump(qapp)
        assert text_of(root, "focusPause") == "Pause"
        assert (float(pause.x()), float(pause.width()), float(skip.x()), float(finish.x())) == before
    finally:
        close_focus(window, focus)


def test_finish_asks_then_ends_the_session_and_leaves_the_screen(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, focus = open_focus(qapp, window)
    asked: list[bool] = []
    focus.endRequested.connect(lambda: asked.append(True))
    try:
        focus.begin()
        focus.finish()
        assert asked == [True]
        assert window.session.focus is not None  # nothing ends until the yes
        assert "min of Quick focus" in focus.endQuestion
        focus.confirmEnd()
        _pump(qapp)
        assert window.session.focus is None
        assert not focus.open
    finally:
        close_focus(window, focus)


def test_back_ends_a_running_session_the_same_way_and_a_ready_screen_just_closes(
    qapp: QApplication, window: NativeWindow
) -> None:
    _root, focus = open_focus(qapp, window)
    asked: list[bool] = []
    focus.endRequested.connect(lambda: asked.append(True))
    try:
        focus.back()
        assert not focus.open and asked == []  # ready: nothing to end
        window._open_focus_screen()
        focus.begin()
        focus.back()
        assert asked == [True] and window.session.focus is not None
        focus.confirmEnd()
        assert window.session.focus is None and not focus.open
    finally:
        close_focus(window, focus)


def test_the_note_says_what_is_on_for_this_session(qapp: QApplication, window: NativeWindow) -> None:
    root, focus = open_focus(qapp, window)
    session = window.session
    try:
        with rules(window, focus_audio="rain"):
            focus.begin()
            _pump(qapp)
            assert text_of(root, "focusNote") == "Alerts muted · Rain"
            session.preferences = {**session.preferences, "focus_auto_mute": False, "focus_audio": "off"}
            focus.refresh()
            _pump(qapp)
            assert text_of(root, "focusNote") == ""
    finally:
        close_focus(window, focus)


def test_a_finished_session_offers_finished_for_open_homework_and_a_break(
    qapp: QApplication, window: NativeWindow
) -> None:
    only = homework(qapp, window, "essay2", 1)[0]
    root, focus = open_focus(qapp, window)
    try:
        assert start(window, only)
        run_out(qapp, window)
        _pump(qapp)
        assert window.session.focus["phase"] == "ended"
        assert text_of(root, "focusPhase") == "Session finished"
        assert _qml(root, "focusFinished").property("visible") is True
        assert _qml(root, "focusTakeBreak").property("visible") is True
        assert _qml(root, "focusPause").property("visible") is False
        focus.markFinished()
        settled(qapp, window)
        assert window.session.assignments["essay2"]["completed"] is True
        assert not focus.open
    finally:
        close_focus(window, focus)


def test_the_number_keys_stay_put_while_focus_covers_the_window_and_work_after(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, focus = open_focus(qapp, window)
    bridge = window._material_page.bridge
    quick = window._material_page._quick
    try:
        bridge.showPage("week")
        root.forceActiveFocus()
        _pump(qapp)
        QTest.keyClick(quick, Qt.Key.Key_4)
        _pump(qapp)
        assert bridge.property("screen") == "week"  # the 4 key is not My day's while Focus is up
        focus.hide()
        _pump(qapp)
        QTest.keyClick(quick, Qt.Key.Key_4)
        _pump(qapp)
        assert bridge.property("screen") == "myday"
    finally:
        bridge.showPage("week")
        close_focus(window, focus)


def test_f_opens_the_screen_from_day(qapp: QApplication, window: NativeWindow) -> None:
    root, focus = open_focus(qapp, window)
    try:
        focus.hide()
        _pump(qapp)
        window._material_page.bridge.showPage("day")
        root.forceActiveFocus()
        _pump(qapp)
        QTest.keyClick(window._material_page._quick, Qt.Key.Key_F)
        _pump(qapp)
        assert focus.open
        assert _qml(root, "materialFocus").property("visible") is True
        assert text_of(root, "focusPhase") == "Ready when you are"
    finally:
        close_focus(window, focus)


def test_start_material_focus_opens_the_screen_on_that_homework(
    qapp: QApplication, window: NativeWindow
) -> None:
    only = homework(qapp, window, "history", 1)[0]
    root = _show_material(qapp, window)
    focus = window._material_page.bridge.focus
    try:
        window.start_material_focus(only["id"], only["days"][0])
        _pump(qapp)
        assert focus.open
        assert text_of(root, "focusTitle") == "History"
        assert _qml(root, "focusPause").property("visible") is True
        assert text_of(root, "focusPause") == "Pause"
    finally:
        close_focus(window, focus)


def test_pause_and_break_hold_ambient_sound_and_finish_stops_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    with rules(window, focus_audio="white-noise"):
        player = window._focus_audio.player
        assert window.session.start_quick_focus()
        assert player.state == "playing" and player.kind == "white-noise"
        window.session.toggle_focus_pause()
        assert player.state == "paused"
        window.session.toggle_focus_pause()
        assert player.state == "playing"
        window.session.advance_focus(False)
        assert window.session.focus["phase"] == "break"
        assert player.state == "paused"
        window.session.reset_focus()
        assert player.state == "stopped"


def test_escape_on_the_screen_goes_back(qapp: QApplication, window: NativeWindow) -> None:
    root, focus = open_focus(qapp, window)
    quick = window._material_page._quick
    try:
        _qml(root, "materialFocus").forceActiveFocus()
        _pump(qapp)
        QTest.keyClick(quick, Qt.Key.Key_Escape)
        _pump(qapp)
        assert not focus.open  # nothing was running, so Back only closes
    finally:
        close_focus(window, focus)


def test_escape_on_the_end_dialog_keeps_the_session_going(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, focus = open_focus(qapp, window)
    quick = window._material_page._quick
    asked: list[bool] = []
    focus.endRequested.connect(lambda: asked.append(True))
    try:
        focus.begin()
        _qml(root, "materialFocus").forceActiveFocus()
        _pump(qapp)
        QTest.keyClick(quick, Qt.Key.Key_Escape)
        _pump(qapp)
        dialog = _qml(root, "focusEndDialog")
        assert asked == [True] and dialog.property("open") is True
        assert window.session.focus is not None and focus.open
        QTest.keyClick(quick, Qt.Key.Key_Escape)
        _pump(qapp)
        assert dialog.property("open") is False
        assert window.session.focus is not None and focus.open
    finally:
        close_focus(window, focus)


def _lineage(item: QObject | None) -> list[str]:
    out: list[str] = []
    while item is not None:
        out.append(item.objectName() or type(item).__name__)
        item = item.parentItem() if hasattr(item, "parentItem") else None
    return out


def _tab_leaks(qapp: QApplication, quick, extra: str | None = None) -> list[tuple[int, list[str]]]:
    scene = quick.quickWindow()
    leaks: list[tuple[int, list[str]]] = []
    for index in range(12):
        QTest.keyClick(quick, Qt.Key.Key_Tab)
        _pump(qapp, 3)
        chain = _lineage(scene.activeFocusItem())
        if "materialFocus" not in chain or (extra and extra not in chain):
            leaks.append((index + 1, chain))
        if "materialFab" in chain or "navWeek" in chain or "materialRail" in chain:
            leaks.append((index + 1, chain))
    return leaks


def test_focus_keeps_tab_inside_ready_running_paused_and_end(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, focus = open_focus(qapp, window)
    quick = window._material_page._quick
    scene = quick.quickWindow()
    try:
        _qml(root, "materialFocus").forceActiveFocus()
        _pump(qapp)
        assert not _tab_leaks(qapp, quick)
        focus.begin()
        _pump(qapp)
        _qml(root, "focusPause").forceActiveFocus()
        _pump(qapp)
        assert not _tab_leaks(qapp, quick)
        focus.togglePause()
        _pump(qapp)
        _qml(root, "focusPause").forceActiveFocus()
        _pump(qapp)
        assert not _tab_leaks(qapp, quick)
        focus.togglePause()
        focus.finish()
        _pump(qapp)
        dialog = _qml(root, "focusEndDialog")
        assert dialog.property("open") is True
        _qml(root, "dialogDismiss").forceActiveFocus()
        _pump(qapp)
        assert not _tab_leaks(qapp, quick, extra="focusEndDialog")
        QTest.keyClick(quick, Qt.Key.Key_Space)
        _pump(qapp)
        assert dialog.property("open") is False
        assert focus.open
        QTest.keyClick(quick, Qt.Key.Key_Escape)
        _pump(qapp)
        assert dialog.property("open") is True
        QTest.keyClick(quick, Qt.Key.Key_Escape)
        _pump(qapp)
        assert dialog.property("open") is False
        focus.confirmEnd()
        _pump(qapp)
        assert not focus.open
        _qml(root, "navWeek").forceActiveFocus()
        _pump(qapp)
        assert "navWeek" in _lineage(scene.activeFocusItem())
    finally:
        close_focus(window, focus)


def _send_key(qapp: QApplication, item: QObject, key: Qt.Key) -> None:
    press = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
    release = QKeyEvent(QEvent.Type.KeyRelease, key, Qt.KeyboardModifier.NoModifier)
    qapp.sendEvent(item, press)
    qapp.sendEvent(item, release)
    _pump(qapp)


def test_enter_and_space_on_focus_act_on_the_visible_layer(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, focus = open_focus(qapp, window)
    bridge = window._material_page.bridge
    start = _qml(root, "focusStart")
    try:
        bridge.showPage("week")
        start.forceActiveFocus()
        _pump(qapp)
        assert start.property("activeFocus") is True
        _send_key(qapp, start, Qt.Key.Key_Space)
        assert focus.open
        assert window.session.focus is not None
        assert window.session.focus["running"] is True
        assert bridge.property("screen") == "week"
        assert window._material_page.bridge.sheets.kind == ""
        pause = _qml(root, "focusPause")
        pause.forceActiveFocus()
        _pump(qapp)
        _send_key(qapp, pause, Qt.Key.Key_Return)
        assert window.session.focus["running"] is False
        assert bridge.property("screen") == "week"
        assert window._material_page.bridge.sheets.kind == ""
    finally:
        close_focus(window, focus)


def _filled_on_screen(root: QObject) -> list[str]:
    """Names of the filled Buttons the student can see on the focus screen right now."""
    from desktop.tests.test_material_window import _visuals

    screen = _qml(root, "materialFocus")
    return [
        str(item.objectName() or item.property("text"))
        for item in _visuals(screen)
        if item.property("kind") == "filled" and item.property("text") is not None and item.isVisible()
    ]


def test_the_focus_screen_shows_one_filled_button_in_every_state(
    qapp: QApplication, window: NativeWindow
) -> None:
    """B3a3 (FIX-SPEC PR 6): one filled button per screen. Ready shows Start, a running or paused session
    shows one of Pause or Resume, never two at once."""
    root, focus = open_focus(qapp, window)
    try:
        assert len(_filled_on_screen(root)) == 1, _filled_on_screen(root)
        focus.begin()
        _pump(qapp)
        assert len(_filled_on_screen(root)) == 1, _filled_on_screen(root)
        focus.togglePause()
        _pump(qapp)
        assert len(_filled_on_screen(root)) == 1, _filled_on_screen(root)
        focus.togglePause()
        _pump(qapp)
        assert len(_filled_on_screen(root)) == 1, _filled_on_screen(root)
    finally:
        close_focus(window, focus)
