"""Material 3 Settings, the Focus, Alerts and This computer pages: each control writes its preference
and the app reacts."""

from __future__ import annotations

import re

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QAccessible, QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from backend import clock as wall_clock
from desktop.native.window import SIGN_OUT_QUESTION, WINDOW_MIN_WIDTH, NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.logic_support import sign_in
from desktop.tests.material_support import quick_of, quick_window_of
from desktop.tests.settings.support_material_settings import (
    _bridge,
    _click,
    _click_segment,
    _material_file,
    _named,
    _open_settings,
    _panel,
    _prefs,
    _pump,
    _texts,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, USERNAME, qapp  # noqa: F401

# ruff: noqa: F811


def test_the_focus_section_writes_audio_and_the_link(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "focus")
    _click_segment(qapp, window, _named(root, "focusAudio")[0], "Rain")
    wait_until(qapp, lambda: _prefs(window).get("focus_audio") == "rain")
    _click_segment(qapp, window, _named(root, "focusAudio")[0], "Spotify")
    wait_until(qapp, lambda: _prefs(window).get("focus_audio") == "spotify")
    _click_segment(qapp, window, _named(root, "focusAudio")[0], "Off")
    wait_until(qapp, lambda: _prefs(window).get("focus_audio") in (None, "off"))

    link = "https://open.spotify.com/playlist/37i9dQZF1DX8Uebhn9wzrS"
    _panel(window).setSpotify("https://example.com/not-spotify")
    assert _panel(window).property("state")["spotifyError"] == "Use a link that starts with https://open.spotify.com."
    assert _prefs(window).get("default_spotify_url") != "https://example.com/not-spotify"
    _panel(window).setSpotify(link)
    wait_until(qapp, lambda: _prefs(window).get("default_spotify_url") == link)
    assert _panel(window).property("state")["spotifyError"] == ""



def test_the_alerts_section_writes_the_reminder_lead(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window, "alerts")
    _click_segment(qapp, window, _named(root, "reminder")[0], "10m")
    wait_until(qapp, lambda: _prefs(window).get("reminder_lead_min") == 10)
    assert _prefs(window).get("reminders_enabled", True) is True
    _click_segment(qapp, window, _named(root, "reminder")[0], "Off")
    wait_until(qapp, lambda: _prefs(window).get("reminders_enabled") is False)
    _click_segment(qapp, window, _named(root, "reminder")[0], "15m")
    wait_until(qapp, lambda: _prefs(window).get("reminders_enabled") is True)
    assert _prefs(window).get("reminder_lead_min") == 15


def test_a_custom_saved_reminder_lead_stays_visible_and_is_not_rewritten_on_open(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = window.session
    session.save_preferences({"reminders_enabled": True, "reminder_lead_min": 17})
    wait_until(qapp, lambda: _prefs(window).get("reminder_lead_min") == 17)
    writes: list[dict] = []
    real = session.save_preferences

    def wrapped(updates: dict, then=None) -> bool:
        writes.append(dict(updates))
        return real(updates, then)

    monkeypatch.setattr(session, "save_preferences", wrapped)
    root = _open_settings(qapp, window, "alerts")
    assert _panel(window).property("state")["reminder"] == "17"
    assert _prefs(window).get("reminder_lead_min") == 17
    assert writes == []
    labels = [str(item.property("text")) for item in _texts(_named(root, "reminder")[0])]
    assert "17m" in labels
    assert "Off" in labels and "5m" in labels and "10m" in labels and "15m" in labels

    _click_segment(qapp, window, _named(root, "reminder")[0], "Off")
    wait_until(qapp, lambda: _prefs(window).get("reminders_enabled") is False)
    assert _prefs(window).get("reminder_lead_min") == 17

    _click_segment(qapp, window, _named(root, "reminder")[0], "10m")
    wait_until(qapp, lambda: _prefs(window).get("reminder_lead_min") == 10)
    assert _prefs(window).get("reminders_enabled") is True


def test_this_computer_login_and_shortcuts(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    applied: list[bool] = []
    monkeypatch.setattr(window, "_apply_start_at_login", applied.append)
    root = _open_settings(qapp, window, "computer")
    bridge = _bridge(window)
    quick = quick_of(window)
    _click(qapp, window, _named(root, "startAtLogin")[0])
    wait_until(qapp, lambda: _prefs(window).get("start_at_login") is True)
    assert applied == [True]

    assert bridge.property("reduceMotion") is False
    assert _named(root, "reduceMotion") == [], "the switch is now Animations, in Look"

    assert bridge.property("shortcuts") is True
    _click(qapp, window, _named(root, "shortcuts")[0])
    wait_until(qapp, lambda: bridge.property("shortcuts") is False)
    assert _material_file()["shortcuts"] is False
    root.forceActiveFocus()
    QTest.keyClick(quick, Qt.Key.Key_2)
    _pump(qapp)
    assert bridge.property("screen") == "settings"
    _click(qapp, window, _named(root, "shortcuts")[0])
    wait_until(qapp, lambda: bridge.property("shortcuts") is True)
    root.forceActiveFocus()
    QTest.keyClick(quick, Qt.Key.Key_2)
    _pump(qapp)
    assert bridge.property("screen") == "week"


def test_this_computer_shows_a_switch_for_the_number_keys_and_one_for_the_letter_keys(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "computer")
    bridge = _bridge(window)
    numbers, letters = _named(root, "row_shortcuts")[0], _named(root, "row_letters")[0]
    assert "1 to 5" in str(numbers.property("subtitle"))
    for key in ("P", "Z", "F"):
        assert key in str(letters.property("subtitle")).split(), key
    assert bridge.property("shortcuts") is True and bridge.property("letterKeys") is False
    assert _named(root, "letters")[0].property("checked") is False, "the letter switch starts off"

    _click(qapp, window, _named(root, "letters")[0])
    wait_until(qapp, lambda: bridge.property("letterKeys") is True)
    assert _material_file()["letters"] is True
    assert _material_file()["shortcuts"] is True, "the number switch was not touched"

    _click(qapp, window, _named(root, "shortcuts")[0])
    wait_until(qapp, lambda: bridge.property("shortcuts") is False)
    assert _material_file()["shortcuts"] is False
    assert _material_file()["letters"] is True, "the letter switch was not touched"

    _click(qapp, window, _named(root, "letters")[0])
    wait_until(qapp, lambda: bridge.property("letterKeys") is False)
    assert _material_file()["letters"] is False


def test_this_computer_account_setup_updates_and_pairing_are_wired(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    heard: list[str] = []
    monkeypatch.setattr(window, "_open_account", lambda: heard.append("account"))
    monkeypatch.setattr(window, "_run_setup_again", lambda: heard.append("setup"))
    monkeypatch.setattr(window, "_check_updates", lambda asked=False: asked and heard.append("updates"))
    seen: list[object] = []

    def begin(done: object) -> bool:
        seen.append(done)
        done({"display_code": "ABCD-1234"}, None)  # type: ignore[operator]
        return True

    monkeypatch.setattr(window.session, "begin_pairing", begin)
    monkeypatch.setattr(
        window.session,
        "pairing_status",
        lambda: {"state": "waiting", "expires_at_ms": wall_clock.now_ms() + 300_000, "tries_left": 3},
    )
    root = _open_settings(qapp, window, "computer")
    _click(qapp, window, _named(root, "row_account")[0])
    _click(qapp, window, _named(root, "row_setup")[0])
    _click(qapp, window, _named(root, "row_updates")[0])
    assert heard == ["account", "setup", "updates"]
    assert _named(root, "row_pair") == [], "pairing lives in Phone & sync"
    root = _open_settings(qapp, window, "sync")
    _click(qapp, window, _named(root, "row_pair")[0])
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "ABCD-1234")
    assert _panel(window).property("state")["pairOpen"] is True
    assert _named(root, "pairingDialog")[0].property("visible") is True
    assert str(_named(root, "pairingCodeText")[0].property("text")) == "ABCD-1234"
    assert "ABCD-1234" in str(_named(root, "row_pair")[0].property("subtitle"))
    _click(qapp, window, _named(root, "pairClose")[0])
    _pump(qapp, 10)
    assert _named(root, "pairingDialog")[0].property("visible") is False


def test_an_open_pairing_code_says_how_long_it_lasts_that_it_works_once_its_tries_and_its_problems(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Findings 3, 5, 6, 7: UI-driven Copy, Start a new code, Close, Escape, focus cycle/restore,
    service loss clearing stale code, pending-callback cancellation, and 320 px layout fit."""
    status: dict | None = {}
    codes = iter(
        [
            "1234 5678",
            "9012 3456",
            "1234 5678",
            "1234 5678",
            "1234 5678",
            "1234 5678",
            "1234 5678",
            "1234 5678",
            "1234 5678",
        ]
    )
    monkeypatch.setattr(
        window.session, "begin_pairing", lambda done: done({"display_code": next(codes)}, None) or True
    )
    monkeypatch.setattr(window.session, "pairing_status", lambda: None if status is None else dict(status))
    root = _open_settings(qapp, window, "sync")
    row = _named(root, "row_pair")[0]
    quick = quick_of(window)
    scene = quick_window_of(window)
    assert quick is not None and scene is not None

    def subtitle() -> str:
        _pump(qapp, 5)
        return str(row.property("subtitle"))

    assert status is not None
    status.update(state="waiting", expires_at_ms=wall_clock.now_ms() + 300_500, tries_left=3)
    _click(qapp, window, row)
    wait_until(qapp, lambda: "1234 5678" in subtitle())
    words = subtitle()
    assert re.search(r"Code works for (5:00|4:59)\. 3 tries left\. It works once\.", words), words
    assert _named(root, "pairingDialog")[0].property("visible") is True
    assert "3 tries left." in str(_named(root, "pairingStatus")[0].property("text"))

    # The code tiles use the bundled mono family: one loaded name, never a fallback list.
    tile = _named(root, "pairingTileFirst")[0]
    digits = next(child for child in tile.childItems() if child.property("text"))
    family = str(digits.property("font").family())
    assert "," not in family, family
    assert "JetBrains" in family, family

    # The steps name the phone's real screen, not a desktop pointer to it.
    shown = [str(item.property("text")) for item in _texts(root)]
    assert any("Pair with your computer" in line for line in shown)
    assert not any("Link a computer" in line for line in shown)

    # Copy code via real UI button writes to the real clipboard.
    QGuiApplication.clipboard().setText("")
    _click(qapp, window, _named(root, "pairCopy")[0])
    assert QGuiApplication.clipboard().text() == "1234 5678"
    assert _panel(window).property("state")["pairCopied"] is True

    # Tab cycles inside the pairing dialog without escaping to the background page.
    # The body fits at this size, so it is not a Tab stop and the cycle skips it.
    body = _named(root, "pairingScroll")[0]
    assert float(body.property("contentHeight")) <= float(body.property("height"))
    assert body.property("activeFocusOnTab") is False
    _named(root, "pairCopy")[0].forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Tab)
    _pump(qapp)
    assert scene.activeFocusItem().objectName() == "pairNewCode"
    QTest.keyClick(quick, Qt.Key.Key_Tab)
    _pump(qapp)
    assert scene.activeFocusItem().objectName() == "pairClose"
    QTest.keyClick(quick, Qt.Key.Key_Tab)
    _pump(qapp)
    assert scene.activeFocusItem().objectName() == "pairCopy"

    # Start a new code via real UI button replaces the displayed code.
    _click(qapp, window, _named(root, "pairNewCode")[0])
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "9012 3456")
    assert str(_named(root, "pairingCodeText")[0].property("text")) == "9012 3456"

    # At 320 px phone width and Larger text, both tiles and both action buttons stay within the viewport.
    dialog = _named(root, "pairingDialog")[0]
    iface = QAccessible.queryAccessibleInterface(dialog)
    assert iface is not None
    assert iface.role() == QAccessible.Role.Dialog
    assert iface.text(QAccessible.Text.Name) == "Pair a phone"
    window.setMinimumWidth(320)
    try:
        _panel(window).setTextSize("larger")
        window.resize(320, 640)
        _pump(qapp, 15)
        scroll = _named(root, "pairingScroll")[0]
        s_left = scroll.mapToScene(QPointF(0, 0)).x()
        s_right = scroll.mapToScene(QPointF(scroll.width(), 0)).x()
        for part_name in ("pairingTileFirst", "pairingTileSecond", "pairCopy", "pairNewCode"):
            part = _named(root, part_name)[0]
            p_left = part.mapToScene(QPointF(0, 0)).x()
            p_right = part.mapToScene(QPointF(part.width(), 0)).x()
            assert p_left >= s_left - 1 and p_right <= s_right + 1, part_name

        # When Larger text makes the card taller than the window, the card is capped and its middle
        # scrolls, but the foot with "Waiting for your phone…" and Close stays inside the card and window.
        for size in ((320, 640), (1024, 640)):
            window.resize(*size)
            _pump(qapp, 15)
            card = _named(root, "pairingCard")[0]
            card_top = card.mapToScene(QPointF(0, 0)).y()
            card_bottom = card.mapToScene(QPointF(0, card.height())).y()
            assert card_top >= 0 and card_bottom <= scene.height(), size
            for part_name in ("pairingFoot", "pairClose"):
                part = _named(root, part_name)[0]
                p_top = part.mapToScene(QPointF(0, 0)).y()
                p_bottom = part.mapToScene(QPointF(0, part.height())).y()
                assert part.property("visible") is True, (size, part_name)
                where = (size, part_name, p_bottom, card_bottom)
                assert p_top >= card_top and p_bottom <= card_bottom + 1, where

        # At Larger text 1024x640 the capped body scrolls from the keyboard to the
        # steps and relay note while Close stays pinned in the foot.
        window.resize(1024, 640)
        _pump(qapp, 15)
        flick = _named(root, "pairingScroll")[0]
        assert flick.property("activeFocusOnTab") is True
        assert float(flick.property("contentHeight")) > float(flick.property("height"))
        flick.forceActiveFocus()
        _pump(qapp)
        assert scene.activeFocusItem().objectName() == "pairingScroll"
        top = float(flick.property("contentY"))
        QTest.keyClick(quick, Qt.Key.Key_End)
        _pump(qapp)
        limit = float(flick.property("contentHeight")) - float(flick.property("height"))
        assert float(flick.property("contentY")) == pytest.approx(limit)
        assert float(flick.property("contentY")) > top
        QTest.keyClick(quick, Qt.Key.Key_PageUp)
        _pump(qapp)
        assert float(flick.property("contentY")) < limit
        QTest.keyClick(quick, Qt.Key.Key_Home)
        _pump(qapp)
        assert float(flick.property("contentY")) == 0
    finally:
        _panel(window).setTextSize("normal")
        window.setMinimumWidth(WINDOW_MIN_WIDTH)
        window.resize(1280, 800)
        _pump(qapp, 10)

    # Escape closes the dialog, clears the code and restores keyboard focus to Pair a phone.
    _named(root, "pairCopy")[0].forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    _pump(qapp, 10)
    assert dialog.property("visible") is False
    assert _panel(window).property("state")["pairCode"] == ""
    assert scene.activeFocusItem().objectName() == "row_pair"

    # Clicking the scrim outside the dialog card also closes it and restores focus to Pair a phone.
    status.update(state="waiting", expires_at_ms=wall_clock.now_ms() + 60_000, tries_left=3)
    _click(qapp, window, row)
    wait_until(qapp, lambda: _panel(window).property("state")["pairOpen"] is True)
    scrim = _named(root, "pairingScrim")[0]
    outside = scrim.mapToScene(QPointF(4, 4)).toPoint()
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(outside))
    _pump(qapp, 10)
    assert dialog.property("visible") is False
    assert _panel(window).property("state")["pairOpen"] is False
    assert _panel(window).property("state")["pairCode"] == ""
    assert subtitle() == "Show a code to link a phone."
    assert scene.activeFocusItem().objectName() == "row_pair"

    # Close via the real UI button closes the dialog, clears the code and restores focus.
    status.update(state="waiting", expires_at_ms=wall_clock.now_ms() + 60_000, tries_left=3)
    _click(qapp, window, row)
    wait_until(qapp, lambda: _panel(window).property("state")["pairOpen"] is True)
    _click(qapp, window, _named(root, "pairClose")[0])
    wait_until(qapp, lambda: _panel(window).property("state")["pairOpen"] is False)
    assert dialog.property("visible") is False
    assert _panel(window).property("state")["pairCode"] == ""
    assert subtitle() == "Show a code to link a phone."
    assert scene.activeFocusItem().objectName() == "row_pair"

    # Service loss (pairing_status returns None) closes & clears stale code with no fake 5:00 countdown.
    # The real watch timer observes it: no direct tick call.
    status.update(state="waiting", expires_at_ms=wall_clock.now_ms() + 60_000, tries_left=3)
    _click(qapp, window, row)
    wait_until(qapp, lambda: _panel(window).property("state")["pairOpen"] is True)
    status = None
    wait_until(qapp, lambda: _panel(window).property("state")["pairOpen"] is False)
    _pump(qapp, 10)
    assert _panel(window).property("state")["pairCode"] == ""
    assert _panel(window).property("state")["pairStatus"] == ""
    assert _panel(window).property("state")["pairError"] != ""
    assert scene.activeFocusItem().objectName() == "row_pair"

    # Countdown expiry and other terminal states close the dialog, clear code, and show the problem.
    # The real watch timer observes each one: no direct tick call.
    for state, problem in (
        ("expired", "That code has expired. Start a new one."),
        ("too_many_tries", "Too many wrong tries. Start a new code."),
        ("idle", "That code isn't active anymore. Start a new one."),
    ):
        status = {"state": "waiting", "expires_at_ms": wall_clock.now_ms() + 60_000, "tries_left": 3}
        _click(qapp, window, row)
        wait_until(qapp, lambda: "1234 5678" in subtitle())
        status = {"state": state}
        wait_until(qapp, lambda: _panel(window).property("state")["pairOpen"] is False, what=state)
        _pump(qapp, 10)
        assert _panel(window).property("state")["pairError"] == problem, state
        assert subtitle() == "Show a code to link a phone.", state
        assert problem in str(_named(root, "row_pairError")[0].property("subtitle")), state


def test_a_second_pairing_start_waits_until_the_first_offer_is_ready(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """New 1: one pairing start in flight at a time; Copy and Start a new code stay
    unavailable until the new offer is ready."""
    pending: list[object] = []
    monkeypatch.setattr(window.session, "begin_pairing", lambda done: pending.append(done) or True)
    monkeypatch.setattr(
        window.session,
        "pairing_status",
        lambda: {"state": "waiting", "expires_at_ms": wall_clock.now_ms() + 300_000, "tries_left": 3},
    )
    root = _open_settings(qapp, window, "sync")
    row = _named(root, "row_pair")[0]
    _click(qapp, window, row)
    wait_until(qapp, lambda: _panel(window).property("state").get("pairStarting") is True)
    assert len(pending) == 1
    assert _named(root, "pairCopy")[0].property("enabled") is False
    assert _named(root, "pairNewCode")[0].property("enabled") is False

    # A second activation while the first start is pending starts nothing new.
    _click(qapp, window, row)
    _pump(qapp, 10)
    assert len(pending) == 1
    assert _panel(window).property("state").get("pairStarting") is True

    # When the first offer lands, the code shows and both buttons come back.
    pending.pop()({"display_code": "1111 2222"}, None)  # type: ignore[operator]
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "1111 2222")
    _pump(qapp)
    assert _panel(window).property("state").get("pairStarting") is False
    assert _named(root, "pairCopy")[0].property("enabled") is True
    assert _named(root, "pairNewCode")[0].property("enabled") is True

    # Restart from the shown dialog, then activate again while that start is pending:
    # the second activation starts nothing new.
    assert _named(root, "pairingDialog")[0].property("visible") is True
    _click(qapp, window, _named(root, "pairNewCode")[0])
    wait_until(qapp, lambda: _panel(window).property("state").get("pairStarting") is True)
    assert len(pending) == 1
    _panel(window).pair()
    _pump(qapp, 10)
    assert len(pending) == 1
    assert _panel(window).property("state").get("pairStarting") is True

    # When the second offer lands, it replaces the shown code and frees both buttons.
    pending.pop()({"display_code": "3333 4444"}, None)  # type: ignore[operator]
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "3333 4444")
    _pump(qapp)
    assert _panel(window).property("state").get("pairStarting") is False
    assert _named(root, "pairCopy")[0].property("enabled") is True
    assert _named(root, "pairNewCode")[0].property("enabled") is True


def test_leaving_settings_clears_a_shown_pairing_code(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """New 2: leaving Settings clears a shown code and countdown like dismissing does,
    so the row cannot show a frozen code."""
    monkeypatch.setattr(
        window.session, "begin_pairing", lambda done: done({"display_code": "1234 5678"}, None) or True
    )
    monkeypatch.setattr(
        window.session,
        "pairing_status",
        lambda: {"state": "waiting", "expires_at_ms": wall_clock.now_ms() + 300_000, "tries_left": 3},
    )
    root = _open_settings(qapp, window, "sync")
    _click(qapp, window, _named(root, "row_pair")[0])
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "1234 5678")
    _bridge(window).showPage("week")
    _pump(qapp)
    assert _panel(window).property("state")["pairCode"] == ""
    assert _panel(window).property("state")["pairStatus"] == ""
    assert _panel(window).property("state")["pairOpen"] is False
    root = _open_settings(qapp, window, "sync")
    _pump(qapp)
    assert str(_named(root, "row_pair")[0].property("subtitle")) == "Show a code to link a phone."


def test_dismissing_or_leaving_settings_cancels_a_pending_pairing_callback(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 6: an in-flight begin_pairing callback must not reopen the dialog after Close or leaving."""
    pending: list[object] = []
    monkeypatch.setattr(window.session, "begin_pairing", lambda done: pending.append(done) or True)
    monkeypatch.setattr(
        window.session,
        "pairing_status",
        lambda: {"state": "waiting", "expires_at_ms": wall_clock.now_ms() + 300_000, "tries_left": 3},
    )
    root = _open_settings(qapp, window, "sync")
    _click(qapp, window, _named(root, "row_pair")[0])
    assert len(pending) == 1
    _panel(window).closePairing()
    pending.pop()({"display_code": "5555 6666"}, None)  # type: ignore[operator]
    _pump(qapp, 10)
    assert _panel(window).property("state")["pairOpen"] is False

    # Starting pairing and leaving Settings to Week before it finishes also ignores the late callback.
    _click(qapp, window, _named(root, "row_pair")[0])
    assert len(pending) == 1
    _bridge(window).showPage("week")
    _pump(qapp)
    pending.pop()({"display_code": "7777 8888"}, None)  # type: ignore[operator]
    _pump(qapp, 10)
    assert _panel(window).property("state")["pairOpen"] is False
    assert _panel(window).property("promptOpen") is False


def test_dismissing_a_pending_start_lets_a_new_pair_show_a_code(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX-LIST-4 item 2: dismissing while a start is pending resets the guard so a new
    Pair works, and the late answer of the old start must not reopen or replace anything."""
    pending: list[object] = []
    monkeypatch.setattr(window.session, "begin_pairing", lambda done: pending.append(done) or True)
    monkeypatch.setattr(
        window.session,
        "pairing_status",
        lambda: {"state": "waiting", "expires_at_ms": wall_clock.now_ms() + 300_000, "tries_left": 3},
    )
    root = _open_settings(qapp, window, "sync")
    _click(qapp, window, _named(root, "row_pair")[0])
    assert len(pending) == 1
    wait_until(qapp, lambda: _panel(window).property("state").get("pairStarting") is True)

    # Dismiss while the first start is still pending, then Pair again: a new start goes out.
    _panel(window).closePairing()
    _pump(qapp)
    assert _panel(window).property("state").get("pairStarting") is False
    _click(qapp, window, _named(root, "row_pair")[0])
    assert len(pending) == 2

    # The new offer shows; the late first answer is stale and changes nothing.
    pending[1]({"display_code": "2222 3333"}, None)  # type: ignore[index]
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "2222 3333")
    assert _panel(window).property("state")["pairOpen"] is True
    pending[0]({"display_code": "1111 0000"}, None)  # type: ignore[index]
    _pump(qapp, 10)
    assert _panel(window).property("state")["pairCode"] == "2222 3333"
    assert _panel(window).property("state")["pairOpen"] is True


def test_leaving_settings_during_a_pending_start_lets_a_new_pair_work(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX-LIST-4 item 2: leaving Settings while a start is pending resets the guard too."""
    pending: list[object] = []
    monkeypatch.setattr(window.session, "begin_pairing", lambda done: pending.append(done) or True)
    monkeypatch.setattr(
        window.session,
        "pairing_status",
        lambda: {"state": "waiting", "expires_at_ms": wall_clock.now_ms() + 300_000, "tries_left": 3},
    )
    root = _open_settings(qapp, window, "sync")
    _click(qapp, window, _named(root, "row_pair")[0])
    assert len(pending) == 1
    wait_until(qapp, lambda: _panel(window).property("state").get("pairStarting") is True)

    _bridge(window).showPage("week")
    _pump(qapp)
    assert _panel(window).property("state").get("pairStarting") is False

    root = _open_settings(qapp, window, "sync")
    _click(qapp, window, _named(root, "row_pair")[0])
    assert len(pending) == 2
    pending[1]({"display_code": "4444 5555"}, None)  # type: ignore[index]
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "4444 5555")
    pending[0]({"display_code": "0000 1111"}, None)  # type: ignore[index]
    _pump(qapp, 10)
    assert _panel(window).property("state")["pairCode"] == "4444 5555"
    assert _panel(window).property("state")["pairOpen"] is True


def test_a_pairing_start_that_raises_leaves_pairing_usable(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX-LIST-4 item 3: a start that raises must not wedge the guard; Copy and
    Start a new code work again on the next Pair."""
    def boom(done: object) -> bool:
        raise RuntimeError("no radio")

    monkeypatch.setattr(window.session, "begin_pairing", boom)
    monkeypatch.setattr(
        window.session,
        "pairing_status",
        lambda: {"state": "waiting", "expires_at_ms": wall_clock.now_ms() + 300_000, "tries_left": 3},
    )
    root = _open_settings(qapp, window, "sync")
    _click(qapp, window, _named(root, "row_pair")[0])
    _pump(qapp, 10)
    assert _panel(window).property("state").get("pairStarting") is False
    assert _panel(window).property("state")["pairError"] == "no radio"

    # Pairing again works and both action buttons come back.
    monkeypatch.setattr(
        window.session, "begin_pairing", lambda done: done({"display_code": "6666 7777"}, None) or True
    )
    _click(qapp, window, _named(root, "row_pair")[0])
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "6666 7777")
    assert _panel(window).property("state").get("pairStarting") is False
    assert _named(root, "pairCopy")[0].property("enabled") is True
    assert _named(root, "pairNewCode")[0].property("enabled") is True


def test_a_pairing_start_that_never_answers_times_out(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX-LIST-4 item 3: a start whose answer never comes must time out instead of
    disabling Copy and Start a new code until restart."""
    import desktop.native.material.bridge_settings as bridge_settings

    monkeypatch.setattr(bridge_settings, "PAIR_START_TIMEOUT_MS", 50)
    pending: list[object] = []
    monkeypatch.setattr(window.session, "begin_pairing", lambda done: pending.append(done) or True)
    monkeypatch.setattr(
        window.session,
        "pairing_status",
        lambda: {"state": "waiting", "expires_at_ms": wall_clock.now_ms() + 300_000, "tries_left": 3},
    )
    root = _open_settings(qapp, window, "sync")
    _click(qapp, window, _named(root, "row_pair")[0])
    wait_until(qapp, lambda: _panel(window).property("state").get("pairStarting") is True)
    wait_until(qapp, lambda: _panel(window).property("state").get("pairStarting") is False)
    assert _panel(window).property("state")["pairError"] == "Pairing did not start."

    # The timed-out start's late answer is stale; a new Pair shows a fresh code.
    _click(qapp, window, _named(root, "row_pair")[0])
    assert len(pending) == 2
    pending[1]({"display_code": "8888 9999"}, None)  # type: ignore[index]
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "8888 9999")
    pending[0]({"display_code": "0000 9999"}, None)  # type: ignore[index]
    _pump(qapp, 10)
    assert _panel(window).property("state")["pairCode"] == "8888 9999"


def test_a_late_answer_of_an_old_start_does_not_free_the_newer_start(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pair, dismiss, Pair again, then the first start answers: the newer start is still pending, so
    Copy and Start a new code stay unavailable and no third start can go out until it answers."""
    pending: list[object] = []
    monkeypatch.setattr(window.session, "begin_pairing", lambda done: pending.append(done) or True)
    monkeypatch.setattr(
        window.session,
        "pairing_status",
        lambda: {"state": "waiting", "expires_at_ms": wall_clock.now_ms() + 300_000, "tries_left": 3},
    )
    root = _open_settings(qapp, window, "sync")
    _click(qapp, window, _named(root, "row_pair")[0])
    _panel(window).closePairing()
    _pump(qapp)
    _click(qapp, window, _named(root, "row_pair")[0])
    assert len(pending) == 2
    wait_until(qapp, lambda: _panel(window).property("state").get("pairStarting") is True)

    pending[0]({"display_code": "1111 0000"}, None)  # type: ignore[index]
    _pump(qapp, 10)
    assert _panel(window).property("state").get("pairStarting") is True
    _panel(window).pair()
    assert len(pending) == 2

    pending[1]({"display_code": "2222 3333"}, None)  # type: ignore[index]
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "2222 3333")
    assert _panel(window).property("state").get("pairStarting") is False


def test_start_a_new_code_that_never_answers_times_out_while_a_code_is_shown(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A code is on screen and Start a new code gets no answer: the timeout still frees Copy and
    Start a new code, and says the new code did not start."""
    import desktop.native.material.bridge_settings as bridge_settings

    monkeypatch.setattr(bridge_settings, "PAIR_START_TIMEOUT_MS", 50)
    pending: list[object] = []
    monkeypatch.setattr(window.session, "begin_pairing", lambda done: pending.append(done) or True)
    monkeypatch.setattr(
        window.session,
        "pairing_status",
        lambda: {"state": "waiting", "expires_at_ms": wall_clock.now_ms() + 300_000, "tries_left": 3},
    )
    root = _open_settings(qapp, window, "sync")
    _click(qapp, window, _named(root, "row_pair")[0])
    pending[0]({"display_code": "4444 5555"}, None)  # type: ignore[index]
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "4444 5555")

    _panel(window).pair()
    assert len(pending) == 2
    wait_until(qapp, lambda: _panel(window).property("state").get("pairStarting") is True)
    wait_until(qapp, lambda: _panel(window).property("state").get("pairStarting") is False)
    assert _panel(window).property("state")["pairError"] == "Pairing did not start."
    # The old code is no longer the one the computer offers: the pop-up closes and drops it, so
    # nothing can copy it, and the Settings row shows why.
    state = _panel(window).property("state")
    assert state["pairOpen"] is False
    assert state["pairCode"] == ""
    assert _named(root, "pairingDialog")[0].property("visible") is False
    assert "Pairing did not start." in str(_named(root, "row_pairError")[0].property("subtitle"))


def test_restarting_a_code_by_keyboard_keeps_focus_in_the_dialog(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX-LIST-4 item 4: keyboard-activating Start a new code disables the focused button;
    focus must stay inside the dialog and land back on Copy code when the offer lands."""
    pending: list[object] = []
    monkeypatch.setattr(window.session, "begin_pairing", lambda done: pending.append(done) or True)
    monkeypatch.setattr(
        window.session,
        "pairing_status",
        lambda: {"state": "waiting", "expires_at_ms": wall_clock.now_ms() + 300_000, "tries_left": 3},
    )
    root = _open_settings(qapp, window, "sync")
    quick = quick_of(window)
    scene = quick_window_of(window)
    assert quick is not None and scene is not None

    _click(qapp, window, _named(root, "row_pair")[0])
    assert len(pending) == 1
    pending.pop()({"display_code": "1234 5678"}, None)  # type: ignore[operator]
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "1234 5678")
    # Let the dialog's deferred focus on Copy code land before moving focus for the test.
    _pump(qapp, 10)
    assert scene.activeFocusItem().objectName() == "pairCopy"

    # Keyboard-activate Start a new code while it is focused.
    _named(root, "pairNewCode")[0].forceActiveFocus()
    _pump(qapp)
    assert scene.activeFocusItem().objectName() == "pairNewCode"
    QTest.keyClick(quick, Qt.Key.Key_Space)
    _pump(qapp, 10)
    wait_until(qapp, lambda: _panel(window).property("state").get("pairStarting") is True)

    # The focused button disabled itself: focus must still be inside the dialog.
    held = scene.activeFocusItem()
    assert held is not None
    assert held.objectName() in ("pairClose", "pairingScroll", "pairCopy", "pairNewCode"), held.objectName()

    # When the new offer lands, focus is back on Copy code.
    pending.pop()({"display_code": "9012 3456"}, None)  # type: ignore[operator]
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "9012 3456")
    wait_until(qapp, lambda: _panel(window).property("state").get("pairStarting") is False)
    _pump(qapp, 5)
    assert scene.activeFocusItem().objectName() == "pairCopy"


def test_this_computer_sign_out_shows_who_is_signed_in_and_asks_before_leaving(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sign out is the row under Account. Cancel stays signed in with Settings still open.
    Sign out runs the same leaving as the More menu, once."""
    out: list[int] = []
    monkeypatch.setattr(window.session, "logout", lambda: out.append(1))
    root = _open_settings(qapp, window, "computer")
    account = _named(root, "row_account")[0]
    row = _named(root, "row_signOut")[0]
    button = _named(root, "signOut")[0]
    name = str(window.session.account["username"])
    rows = [
        str(child.objectName())
        for child in row.parentItem().childItems()
        if str(child.objectName()).startswith("row_")
    ]
    assert rows[rows.index("row_account") + 1] == "row_signOut"
    assert str(account.property("subtitle")) == "Name, password, recovery codes and your files."
    assert str(row.property("title")) == "Sign out"
    assert str(row.property("subtitle")) == f"Signed in as {name}. Your week is saved first."
    assert str(button.property("text")) == "Sign out"
    assert button.property("enabled") is True

    _click(qapp, window, button)
    sheets = _bridge(window).sheets
    ask = dict(sheets.property("ask"))
    assert ask["id"] == "sign-out"
    assert ask["title"] == "Sign out"
    assert ask["body"] == SIGN_OUT_QUESTION.format(where="this computer")
    assert [answer["label"] for answer in ask["answers"]] == ["Cancel", "Sign out"]
    sheets.answer("stay")
    _pump(qapp, 20)
    assert out == []
    assert window.session.account is not None
    assert dict(sheets.property("ask")) == {}
    assert _bridge(window).property("screen") == "settings"
    assert _panel(window).property("state")["section"] == "computer"

    _click(qapp, window, _named(root, "signOut")[0])
    sheets.answer("yes")
    _pump(qapp, 20)
    assert out == [1]
    assert dict(sheets.property("ask")) == {}


def test_this_computer_sign_out_is_disabled_while_the_session_is_busy(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr(window, "_log_out", lambda: asked.append("signOut"))
    root = _open_settings(qapp, window, "computer")
    button = _named(root, "signOut")[0]
    assert button.property("enabled") is True
    built: list[str] = []
    _panel(window).changed.connect(lambda: built.append("changed"))
    window.session.busy = True
    try:
        window.session.busy_changed.emit(True)
        _pump(qapp, 20)
        assert button.property("enabled") is False
        assert built == [], "a busy toggle rebuilds Settings"
        _panel(window).signOut()
        assert asked == []
        assert dict(_bridge(window).sheets.property("ask")) == {}
    finally:
        window.session.busy = False
        window.session.busy_changed.emit(False)
    _pump(qapp, 20)
    assert button.property("enabled") is True
    assert built == [], "clearing busy rebuilds Settings"


def test_the_sign_out_row_does_not_name_a_missing_account(
    qapp: QApplication, window: NativeWindow
) -> None:
    """No account name means the row says the week is saved, and nothing else."""
    root = _open_settings(qapp, window, "computer")
    row = _named(root, "row_signOut")[0]
    held = dict(window.session.account)
    window.session.account = {"id": held["id"]}
    window.session.week_changed.emit()
    _pump(qapp)
    subtitle = str(row.property("subtitle"))
    assert subtitle == "Your week is saved first."
    assert "Signed in as ." not in subtitle
    for item in _texts(row):
        assert "Signed in as ." not in str(item.property("text"))
    window.session.account = held


def test_signing_out_of_this_computer_opens_the_week_without_the_old_drafts(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Sign out, then sign in: Week is showing, and the drafts left in Settings are gone."""
    root = _open_settings(qapp, window, "computer")
    panel = _panel(window)
    panel.addWorkCustom()
    panel.toggleSchoolDay(6)
    panel.setSpotify("not-a-link")
    saved_clock = (window.session.preferences or {}).get("clock_24h") is True
    panel._sync_problem = "Sync failed: the old phone"
    panel._unsaved = {"clock_24h": not saved_clock}
    panel.setReminderLead(999)
    _pump(qapp)
    before = panel.property("state")
    assert before["section"] == "computer"
    assert before["studyDirty"] is True
    assert before["schoolDirty"] is True
    assert before["spotifyError"] == "Use a link that starts with https://open.spotify.com."
    assert before["notice"] == "Couldn't save that change. Try again."
    assert before["syncProblem"] == "Sync failed: the old phone"
    assert before["clock24"] is not saved_clock

    _click(qapp, window, _named(root, "signOut")[0])
    # Left for last: the remove-phone prompt covers This computer and would take the click above.
    panel._remove_ask = {"id": "old", "name": "Old phone"}
    panel._publish()
    assert panel.property("state")["askRemove"] is True
    _bridge(window).sheets.answer("yes")
    wait_until(qapp, lambda: window.session.account is None and not window.session.busy)
    _pump(qapp)
    page = window._material_page
    assert page is not None and page.root is not None
    signed_out_rows = _named(page.root, "row_signOut")
    if signed_out_rows:
        assert str(signed_out_rows[0].property("subtitle")) == "Your week is saved first."
    for item in _texts(page.root):
        assert "Signed in as ." not in str(item.property("text"))

    sign_in(qapp, window, USERNAME, PASSWORD)
    wait_until(
        qapp,
        lambda: window.session.account is not None
        and window.session.preferences is not None
        and not window.session.busy,
    )
    _pump(qapp)
    assert _bridge(window).property("screen") == "week"
    state = panel.property("state")
    assert state["section"] == "look"
    assert state["page"] == "sections"
    assert state["studyDirty"] is False
    assert state["schoolDirty"] is False
    assert state["notice"] == ""
    assert state["spotifyError"] == ""
    assert state["syncProblem"] == ""
    assert state["askRemove"] is False
    assert state["clock24"] is ((window.session.preferences or {}).get("clock_24h") is True)
