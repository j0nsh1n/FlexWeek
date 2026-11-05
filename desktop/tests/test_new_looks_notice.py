"""The one-time 1.0.0 look notice belongs to existing accounts on this device."""

from __future__ import annotations

import importlib.util
import json
import os
import time
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QStandardPaths, Qt
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QPushButton, QWidget

    from desktop.native.look import AA_TEXT, resolved_palette, sanitize_look, toast_colours
    from desktop.native.tokens import contrast
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer

PASSWORD = "a-long-test-password"
NOTICE = "New in 1.0.0: each design has its own looks."


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-new-looks-notice-test"])
    yield application


def wait_until(qapp: QApplication, predicate, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was still false")


def device_look_file() -> Path:
    root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(root) / "flexweek-look.json"


def make_new_account(qapp: QApplication, server: LocalServer, username: str) -> NativeWindow:
    made = NativeWindow(server.origin)
    made.show()
    made.username.setText(username)
    made.password.setText(PASSWORD)
    made.findChild(QPushButton, "createAccount").click()
    wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "recoveryPage")
    made.recovery_ack.setChecked(True)
    made.recovery_continue.click()
    wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "setupPage")
    made.setup_page.skip_all.click()
    wait_until(
        qapp,
        lambda: made._stack.currentWidget().objectName() == "weekPage"
        and made.session.preferences is not None
        and not made.session.busy
        and not made._setup_prefs,
    )
    return made


@pytest.fixture()
def server(qapp: QApplication, tmp_path: Path) -> Iterator[LocalServer]:
    device_look_file().unlink(missing_ok=True)
    running = LocalServer(tmp_path / "new-looks.db")
    running.start()
    yield running
    running.stop()


@pytest.fixture()
def fresh_window(qapp: QApplication, server: LocalServer) -> Iterator[NativeWindow]:
    made = make_new_account(qapp, server, "looks_fresh")
    yield made
    made.session.client.reset()
    made.hide()
    made.close()
    qapp.processEvents()


def make_legacy_account(window: NativeWindow) -> None:
    """Model a finished pre-1.0 account whose device file has no design look choices."""
    assert window.session.preferences["setup"].get("finished_at")
    saved = json.loads(device_look_file().read_text())
    saved["layout"] = {"main": "classic", "day": "dial", "options": {}}
    saved.pop("new_look_notice_exempt", None)
    saved.pop("new_look_notice_seen", None)
    device_look_file().write_text(json.dumps(saved) + "\n")
    window.session.new_account = False
    window._load_look()


def test_an_existing_pre_100_account_sees_the_notice_once_on_its_first_planner_open(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    preferences = deepcopy(window.session.preferences)
    look = deepcopy(window._look)
    planner_geometry = window.planner.geometry()

    window._on_week()

    assert window.toast.isVisible()
    assert window.toast.text() == NOTICE
    assert window.toast.button.text() == "Choose a look"
    # One action and the x: "Not now" is gone, the x does what it did (UI21).
    assert not window.toast.secondary_button.isVisibleTo(window.toast)
    assert window.toast.close_button.isVisibleTo(window.toast)
    assert str(window.session.account["id"]) not in window._new_look_notice_seen
    assert window.session.preferences == preferences
    assert window._look == look
    assert window.planner.geometry() == planner_geometry
    window._on_week()
    assert window.toast.isVisible() and window.toast.text() == NOTICE


def test_a_fresh_account_does_not_see_the_notice_after_setup(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    assert fresh_window.session.preferences["setup"].get("finished_at")
    assert fresh_window.session.new_account
    fresh_window._on_week()
    assert fresh_window.toast.text() != NOTICE
    account_id = str(fresh_window.session.account["id"])
    assert account_id not in fresh_window._new_look_notice_seen
    assert account_id in fresh_window._new_look_notice_exempt
    fresh_window.session.new_account = False
    fresh_window._load_look()
    fresh_window._on_week()
    assert fresh_window.toast.text() != NOTICE


def test_esc_closes_the_notice_for_that_account_on_this_device(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    """A18/UI21: Esc is the x, from whatever notice button holds focus."""
    window = fresh_window
    make_legacy_account(window)
    window._on_week()
    account_id = str(window.session.account["id"])
    window.toast.button.setFocus()
    qapp.processEvents()
    QTest.keyClick(window.toast.button, Qt.Key.Key_Escape)

    assert not window.toast.isVisible()
    assert account_id in window._new_look_notice_seen
    stored = json.loads(device_look_file().read_text())
    assert account_id in stored["new_look_notice_seen"]
    window._load_look()
    window._on_week()
    assert not window.toast.isVisible()


def test_tab_reaches_the_notice_s_button_and_its_x(qapp: QApplication, fresh_window: NativeWindow) -> None:
    window = fresh_window
    make_legacy_account(window)
    # An empty week shows its welcome, with no hours canvas for the notice's Tab chain to start from.
    window.session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 240,
            "days": [0, 1, 2, 3, 4],
        }
    )
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    window._on_week()
    canvas = next(surface for surface in window._week_surfaces() if surface.isVisible())
    canvas.setFocus()
    qapp.processEvents()
    QTest.keyClick(canvas, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is window.toast.button
    QTest.keyClick(window.toast.button, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is window.toast.close_button


def test_the_notice_is_a_card_of_the_look_not_the_dark_toast(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    """UI21: B3a3's card, not decision 20's dark toast — the card colour, its 8 px corners and a
    1 px edge."""
    window = fresh_window
    make_legacy_account(window)
    window._on_week()
    card = window.toast.card
    card.ensurePolished()
    qapp.processEvents()
    pack, dark, accent = window._look_inputs()
    palette = resolved_palette(pack, dark, window._look, accent)
    picture = card.grab().toImage()
    middle = picture.height() // 2
    assert picture.pixelColor(0, middle).name() == palette["hairline"], "the 1 px edge"
    assert picture.pixelColor(1, 1).alpha() < 255, "the corner is rounded, not the sheet's 16 px"
    spots = [picture.pixelColor(8, y).name() for y in (4, 6, 8)]
    assert palette["panel"] in spots, (palette["panel"], spots)


def test_choose_a_look_dismisses_the_notice_and_opens_settings_at_look(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    window._on_week()
    account_id = window.session.account["id"]
    preferences = deepcopy(window.session.preferences)
    look = deepcopy(window._look)
    layout = deepcopy(window._layout)
    window.toast.button.click()

    assert str(account_id) in window._new_look_notice_seen
    assert window._stack.currentWidget() is window._settings
    assert window._settings.nav.currentRow() == 0
    assert window._settings.nav.currentItem().text() == "Look"
    assert window.session.preferences == preferences
    assert window._look == look
    assert window._layout == layout
    stored = json.loads(device_look_file().read_text())
    assert str(account_id) in stored["new_look_notice_seen"]
    window._close_settings(save=False)
    window._load_look()
    window._on_week()
    assert not window.toast.isVisible()


def test_closing_the_notice_keeps_it_dismissed_on_this_device(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    window._on_week()
    account_id = str(window.session.account["id"])
    window.toast.close_button.click()

    assert not window.toast.isVisible()
    assert account_id in window._new_look_notice_seen
    stored = json.loads(device_look_file().read_text())
    assert account_id in stored["new_look_notice_seen"]
    window._load_look()
    window._on_week()
    assert not window.toast.isVisible()


def test_an_account_with_any_saved_design_look_does_not_get_the_notice(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    saved = json.loads(device_look_file().read_text())
    saved["layout"]["options"] = {"classic": {"look": "your"}}
    device_look_file().write_text(json.dumps(saved) + "\n")
    window._load_look()
    window._on_week()

    assert window.toast.text() != NOTICE
    assert str(window.session.account["id"]) not in window._new_look_notice_seen


def _card_ground(card: QWidget) -> str:
    picture = card.grab().toImage()
    return picture.pixelColor(max(8, card.width() - 10), max(8, card.height() - 10)).name()


def _reading(widget: QWidget, ground: str, role: QPalette.ColorRole) -> tuple[str, str]:
    """Palette colour plus the colour actually painted, skipping the card ground."""
    widget.ensurePolished()
    pal = widget.palette().color(role).name()
    picture = widget.grab().toImage()
    skip = QColor(ground)
    counts: dict[str, int] = {}
    for x in range(picture.width()):
        for y in range(picture.height()):
            pixel = picture.pixelColor(x, y)
            if pixel.alpha() < 200:
                continue
            if (
                abs(pixel.red() - skip.red())
                + abs(pixel.green() - skip.green())
                + abs(pixel.blue() - skip.blue())
                < 40
            ):
                continue
            name = pixel.name()
            counts[name] = counts.get(name, 0) + 1
    painted = max(counts, key=counts.get) if counts else pal
    return painted, pal


def test_the_notice_card_words_and_actions_read_on_the_card(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    """The message, Choose a look and the close x sit over the card, not inside it, so they take the
    card's colours as a property. Text and the x reach 4.5:1 on the card, the action in the accent
    does too, in Light, Dark and High contrast. An ordinary toast keeps its own colours."""
    window = fresh_window
    window.resize(1280, 800)
    window.session.preferences = {**window.session.preferences, "motion": "off"}
    looks = (
        ("light-frost", "default"),
        ("dark-frost", "default"),
        ("light-frost", "high-contrast"),
    )
    for pack, preset in looks:
        window.session.preferences = {**window.session.preferences, "theme_pack": pack}
        window._look = sanitize_look({"preset": preset})
        window._apply_appearance()
        qapp.processEvents()
        palette = resolved_palette(pack, pack == "dark-frost", window._look, "default")
        window.toast.show_message(
            NOTICE,
            "Choose a look",
            lambda: None,
            close_callback=lambda: None,
            card=True,
        )
        qapp.processEvents()
        ground = _card_ground(window.toast.card)
        for widget, role, expected in (
            (window.toast.label, QPalette.ColorRole.WindowText, palette["text"]),
            (window.toast.button, QPalette.ColorRole.ButtonText, palette["accent_text"]),
            (window.toast.close_button, QPalette.ColorRole.ButtonText, palette["muted"]),
        ):
            painted, pal = _reading(widget, ground, role)
            assert contrast(painted, ground) >= AA_TEXT, (pack, preset, widget.objectName(), painted, ground)
            assert contrast(pal, ground) >= AA_TEXT, (pack, preset, widget.objectName(), pal, ground)
            assert pal == expected, (pack, preset, widget.objectName(), pal, expected)
        window.toast.hide()

    window.session.preferences = {**window.session.preferences, "theme_pack": "light-frost"}
    window._look = sanitize_look({"preset": "default"})
    window._apply_appearance()
    qapp.processEvents()
    palette = resolved_palette("light-frost", False, window._look, "default")
    toast = toast_colours(palette)
    window.toast.show_message("Placed 1 homework block.", "Undo", lambda: None)
    qapp.processEvents()
    _, action = _reading(window.toast.button, toast["background"], QPalette.ColorRole.ButtonText)
    _, words = _reading(window.toast.label, toast["background"], QPalette.ColorRole.WindowText)
    assert action == toast["action"]
    assert words == toast["text"]
    window.toast.hide()
