"""Material 3 alarms, step 4b: the Alarms group in Settings > Alerts, the add and edit sheet, and the
screen an alarm rings on. Expected values are the rules' (backend AlarmPreference: 20 alarms at most, at
least one day, a Spotify share link) and what the Widgets card and ring dialog do, not what the code
prints."""

from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.day.support_layouts_window import SPOTIFY_TRACK, RingRecorder
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_material_settings import (
    _bridge,
    _click,
    _named,
    _open_settings,
    _panel,
    _prefs,
    _pump,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811

NO_DAY = "Pick at least one day"
BAD_LINK = "Use an https://open.spotify.com share link."


def _sheets(window: NativeWindow) -> QObject:
    return _bridge(window).sheets


def _form(window: NativeWindow) -> dict:
    return dict(_sheets(window).property("form"))


def _alarms(window: NativeWindow) -> list[dict]:
    return list(_prefs(window).get("alarms") or [])


def _add(
    qapp: QApplication, window: NativeWindow, name: str, hour: int, minute: int, days: list[int]
) -> None:
    """Add an alarm through the sheet, as the student does. The sheet opens on Monday to Friday."""
    sheets = _sheets(window)
    before = len(_alarms(window))
    sheets.openAlarm("")
    sheets.setAlarmText("name", name)
    sheets.setAlarmNumber("hour", hour)
    sheets.setAlarmNumber("minute", minute)
    for day in range(7):
        if (day in range(5)) != (day in days):
            sheets.toggleAlarmDay(day)
    sheets.saveAlarm()
    wait_until(qapp, lambda: len(_alarms(window)) == before + 1, what="the alarm to be saved")


def _rig(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> RingRecorder:
    recorder = RingRecorder()
    window._bell = recorder
    monkeypatch.setattr(window._spotify, "play", lambda _url: None)
    return recorder


def _ring(window: NativeWindow, alarm: dict) -> None:
    window.session._enqueue_alarm(alarm)


# Add, edit, remove


def test_an_alarm_added_in_the_sheet_is_saved_and_listed(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window, "alerts")
    assert _panel(window).property("state")["alarms"] == []
    _add(qapp, window, "Wake up", 6, 45, [0, 1, 2])
    (alarm,) = _alarms(window)
    assert (alarm["name"], alarm["time"], alarm["days"], alarm["enabled"]) == (
        "Wake up",
        "06:45",
        [0, 1, 2],
        True,
    )
    assert alarm["sound"] == "chime" and alarm["spotify_url"] is None
    assert _sheets(window).property("kind") == ""
    (row,) = dict(_panel(window).property("state"))["alarms"]
    assert row["id"] == alarm["id"]
    assert row["title"] == "Wake up · Chime"
    assert row["subtitle"].endswith("Mon, Tue and Wed")
    _pump(qapp)
    assert _named(root, "row_alarm_" + alarm["id"])


def test_the_alarm_hour_picker_follows_the_twelve_or_twenty_four_hour_setting(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "alerts")
    sheets = _sheets(window)
    window.session.preferences["clock_24h"] = False
    sheets.openAlarm("")
    labels = [item["label"] for item in _form(window)["hours"]]
    assert labels[0] == "12 AM" and labels[7] == "7 AM" and labels[12] == "12 PM" and labels[16] == "4 PM"
    assert [item["value"] for item in _form(window)["hours"]] == list(range(24)), "the saved hour is still 0 to 23"
    sheets.closeSheet()
    window.session.preferences["clock_24h"] = True
    sheets.openAlarm("")
    assert [item["label"] for item in _form(window)["hours"]][16] == "16"


def test_a_picked_alarm_day_shows_a_check_and_an_unpicked_one_does_not(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "alerts")
    _sheets(window).openAlarm("")
    _pump(qapp, 20)
    checks = _named(root, "alarmDayCheck")
    assert len([c for c in checks if c.property("visible")]) == 5, "Monday to Friday are picked"
    _sheets(window).toggleAlarmDay(5)
    _pump(qapp, 10)
    assert len([c for c in _named(root, "alarmDayCheck") if c.property("visible")]) == 6


def test_a_blank_name_is_called_alarm(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "alerts")
    _add(qapp, window, "   ", 7, 0, [0])
    assert _alarms(window)[0]["name"] == "Alarm"


def test_an_alarm_is_edited_in_place(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "alerts")
    _add(qapp, window, "Wake up", 6, 45, [0, 1, 2])
    alarm_id = _alarms(window)[0]["id"]
    sheets = _sheets(window)
    sheets.openAlarm(alarm_id)
    assert _form(window)["heading"] == "Edit alarm" and _form(window)["name"] == "Wake up"
    sheets.setAlarmText("name", "Practice")
    sheets.setAlarmText("sound", "glass")
    sheets.setAlarmEnabled(False)
    sheets.saveAlarm()
    wait_until(qapp, lambda: _alarms(window)[0]["name"] == "Practice")
    (alarm,) = _alarms(window)
    assert (alarm["id"], alarm["sound"], alarm["enabled"], alarm["time"]) == (
        alarm_id,
        "glass",
        False,
        "06:45",
    )
    assert dict(_panel(window).property("state"))["alarms"][0]["title"] == "Practice · Glass · off"


def test_an_alarm_is_removed_only_after_the_question_is_answered(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "alerts")
    _add(qapp, window, "Wake up", 6, 45, [0])
    sheets = _sheets(window)
    sheets.openAlarm(_alarms(window)[0]["id"])
    sheets.removeAlarm()
    assert dict(sheets.property("ask"))["id"] == "delete-alarm"
    sheets.answer("stay")
    _pump(qapp)
    assert len(_alarms(window)) == 1 and sheets.property("kind") == "alarm"
    sheets.removeAlarm()
    sheets.answer("delete")
    wait_until(qapp, lambda: _alarms(window) == [])
    assert sheets.property("kind") == ""


def test_closing_a_changed_sheet_asks_before_dropping_it(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "alerts")
    sheets = _sheets(window)
    sheets.openAlarm("")
    sheets.closeSheet()
    assert sheets.property("kind") == ""
    sheets.openAlarm("")
    sheets.setAlarmText("name", "Typed")
    sheets.closeSheet()
    assert dict(sheets.property("ask"))["id"] == "discard"
    sheets.answer("discard")
    assert sheets.property("kind") == "" and _alarms(window) == []


# Limits


def test_an_alarm_on_no_day_is_refused_with_the_widgets_words(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "alerts")
    sheets = _sheets(window)
    sheets.openAlarm("")
    for day in range(5):
        sheets.toggleAlarmDay(day)
    sheets.saveAlarm()
    _pump(qapp)
    assert _form(window)["daysProblem"] == NO_DAY
    assert sheets.property("kind") == "alarm" and _alarms(window) == []
    sheets.toggleAlarmDay(0)
    assert _form(window)["daysProblem"] == ""


def test_a_link_that_is_not_a_spotify_share_link_is_refused(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "alerts")
    sheets = _sheets(window)
    sheets.openAlarm("")
    sheets.setAlarmText("link", "https://example.org/song")
    sheets.saveAlarm()
    _pump(qapp)
    assert _form(window)["linkProblem"] == BAD_LINK and _alarms(window) == []
    sheets.setAlarmText("link", SPOTIFY_TRACK)
    sheets.setAlarmText("sound", "spotify")
    sheets.saveAlarm()
    wait_until(qapp, lambda: len(_alarms(window)) == 1)
    assert _alarms(window)[0]["spotify_url"] == SPOTIFY_TRACK and _alarms(window)[0]["sound"] == "spotify"


def test_a_twenty_first_alarm_is_not_started(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "alerts")
    twenty = [
        {"id": f"a{n}", "name": f"Alarm {n}", "time": "07:00", "days": [0], "enabled": True, "sound": "chime"}
        for n in range(20)
    ]
    window.session.save_preferences({"alarms": twenty})
    wait_until(qapp, lambda: len(_alarms(window)) == 20)
    sheets = _sheets(window)
    sheets.openAlarm("")
    _pump(qapp)
    assert sheets.property("kind") == ""
    assert sheets.property("notice") == "You can have up to 20 alarms."
    assert dict(_panel(window).property("state"))["alarmsFull"] is True
    sheets.openAlarm("a3")
    assert sheets.property("kind") == "alarm"


# The sheet and the section on screen


def test_the_add_button_opens_the_sheet_and_the_section_lists_the_alarm(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "alerts")
    (add,) = _named(root, "addAlarm")
    _click(qapp, window, add)
    wait_until(qapp, lambda: _sheets(window).property("kind") == "alarm")
    assert window._material_page.root.findChild(QObject, "alarmSheet") is not None


# The ring screen


def test_an_alarm_rings_on_the_material_screen_and_never_in_the_widgets_dialog(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _open_settings(qapp, window, "alerts")
    recorder = _rig(window, monkeypatch)

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the Widgets ring dialog opened over Material")

    monkeypatch.setattr("desktop.native.window.AlarmRingDialog", refuse)
    window.session.preferences = {**(window.session.preferences or {}), "alert_volume": 45}
    _ring(window, {"id": "a1", "name": "Practice", "time": "07:00", "sound": "glass"})
    _pump(qapp)
    ring = _bridge(window).ring
    assert ring.property("open") is True and window._alarm_dialog is None
    form = dict(ring.property("form"))
    assert form["title"] == "Practice" and "Alarm is ringing" in form["detail"] and form["spotify"] is False
    assert form["snoozeLabel"] == "Snooze 5 minutes"
    assert recorder.started == [("glass", 45)]
    screen = root.findChild(QObject, "ringScreen")
    assert screen is not None and screen.property("visible") is True
    assert _named(root, "ringDismiss") and _named(root, "ringSnooze")


def test_the_ring_screen_in_dark_dims_the_page_harder_and_draws_the_card_edge(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtQml import QQmlProperty

    seen = {}
    for mode in ("light", "dark"):
        look_file().write_text(json.dumps({"material": {"mode": mode}}))
        root = _open_settings(qapp, window, "alerts")
        _rig(window, monkeypatch)
        _ring(window, {"id": mode, "name": "Practice", "time": "07:00", "sound": "low"})
        _pump(qapp)
        seen[mode] = (
            float(_named(root, "ringScrim")[0].property("opacity")),
            float(QQmlProperty(_named(root, "ringCard")[0], "border.width").read()),
        )
        _bridge(window).ring.dismiss()
        _pump(qapp)
    assert seen["light"] == (0.32, 0.0)
    assert seen["dark"] == (0.7, 1.0)


def test_dismiss_stops_the_noise_and_does_not_snooze(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _open_settings(qapp, window, "alerts")
    recorder = _rig(window, monkeypatch)
    _ring(window, {"id": "a1", "name": "Practice", "time": "07:00", "sound": "low"})
    _pump(qapp)
    (dismiss,) = _named(root, "ringDismiss")
    _click(qapp, window, dismiss)
    assert _bridge(window).ring.property("open") is False
    assert recorder.ringing is False and recorder.stops >= 1
    assert window.session.active_alarm is None and "a1" not in window.session.snoozed_alarms
    assert window._alarm_on_material is False


def test_snooze_does_what_the_dialog_snooze_does(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _open_settings(qapp, window, "alerts")
    recorder = _rig(window, monkeypatch)
    _ring(window, {"id": "a1", "name": "Practice", "time": "07:00", "sound": "low"})
    _pump(qapp)
    now = window.session.now_ms()
    (snooze,) = _named(root, "ringSnooze")
    _click(qapp, window, snooze)
    assert _bridge(window).ring.property("open") is False and recorder.ringing is False
    # The Widgets snooze is five minutes from now (ALARM_SNOOZE_MS = 300000).
    wait = window.session.snoozed_alarms["a1"] - now
    assert 4 * 60_000 < wait <= 5 * 60_000 + 5_000


def test_a_second_alarm_rings_after_the_first_is_answered(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_settings(qapp, window, "alerts")
    _rig(window, monkeypatch)
    _ring(window, {"id": "a1", "name": "First", "time": "07:00", "sound": "low"})
    _ring(window, {"id": "a2", "name": "Second", "time": "07:00", "sound": "low"})
    ring = _bridge(window).ring
    assert dict(ring.property("form"))["title"] == "First"
    ring.dismiss()
    _pump(qapp)
    assert ring.property("open") is True and dict(ring.property("form"))["title"] == "Second"
    ring.dismiss()
    assert ring.property("open") is False


def test_a_spotify_alarm_offers_the_link_and_shows_what_plays(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_settings(qapp, window, "alerts")
    _rig(window, monkeypatch)
    opened: list[str] = []
    monkeypatch.setattr(
        "desktop.native.material.bridge_alarms.open_in_app", lambda url: opened.append(url) or True
    )
    _ring(
        window,
        {"id": "a1", "name": "Wake up", "time": "07:00", "sound": "spotify", "spotify_url": SPOTIFY_TRACK},
    )
    ring = _bridge(window).ring
    assert dict(ring.property("form"))["spotify"] is True
    ring.openSpotify()
    assert opened == [SPOTIFY_TRACK]
    window._spotify_heard("Playing Song")
    assert dict(ring.property("form"))["playing"] == "Playing Song"
    ring.dismiss()


def test_escape_and_enter_dismiss_as_the_dialog_does(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_settings(qapp, window, "alerts")
    _rig(window, monkeypatch)
    quick = window._material_page._quick
    ring = _bridge(window).ring
    for key in (Qt.Key.Key_Escape, Qt.Key.Key_Return):
        _ring(window, {"id": f"k{int(key)}", "name": "Keys", "time": "07:00", "sound": "low"})
        _pump(qapp)
        assert ring.property("open") is True
        QTest.keyClick(quick, key)
        wait_until(qapp, lambda: ring.property("open") is False, what=f"{key} to dismiss")
        assert window.session.active_alarm is None


def test_on_widgets_the_alarm_still_opens_the_dialog(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window._surface = "widgets"
    _rig(window, monkeypatch)
    opened: list[object] = []
    monkeypatch.setattr("desktop.native.window.AlarmRingDialog.exec", lambda self: opened.append(self) or 0)
    window._on_alarm({"id": "w1", "name": "Practice", "time": "07:00", "sound": "low"})
    assert len(opened) == 1 and window._alarm_on_material is False


def test_closing_the_window_stops_an_alarm_ringing_on_material(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_settings(qapp, window, "alerts")
    recorder = _rig(window, monkeypatch)
    _ring(window, {"id": "c1", "name": "Practice", "time": "07:00", "sound": "low"})
    _pump(qapp)
    assert recorder.ringing is True and window._alarm_on_material is True
    window._saved_to_leave = True
    window._tray_icon = None
    window.close()
    assert recorder.ringing is False
    assert window._alarm_on_material is False


def test_material_giving_up_stops_an_alarm_ringing_on_its_screen(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_settings(qapp, window, "alerts")
    recorder = _rig(window, monkeypatch)
    monkeypatch.setattr("desktop.native.window.cpu_drawing.drawing_on_cpu", lambda: True)
    _ring(window, {"id": "g1", "name": "Practice", "time": "07:00", "sound": "low"})
    _pump(qapp)
    assert recorder.ringing is True
    window._give_up_material()
    assert recorder.ringing is False
    assert window._alarm_on_material is False
