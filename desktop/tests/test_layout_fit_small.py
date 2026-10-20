"""The smallest window the app is meant for, 1024 x 640, at Large text: Clay's card in front stays whole
on the screen and the window keeps its size."""

from __future__ import annotations

import contextlib
import importlib.util
import os
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

    from desktop.native.layouts.clay import slots
    from desktop.native.layouts.registry import sanitize_layout
    from desktop.native.look import sanitize_look
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer
    from desktop.tests.logic_support import past_setup

PASSWORD = "a-long-test-password"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-fit-small-test"])
    yield application


def wait_until(qapp: QApplication, predicate: Callable[[], bool], timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was still false")


@pytest.fixture()
def window(qapp: QApplication, tmp_path: Path) -> Iterator[NativeWindow]:
    """Signed in on the week page with setup skipped, as the other window tests start."""
    server = LocalServer(tmp_path / "flexweek.db")
    server.start()
    made = NativeWindow(server.origin)
    made.show()
    try:
        made.username.setText("fit_student")
        made.password.setText(PASSWORD)
        made.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "recoveryPage")
        made.recovery_ack.setChecked(True)
        made.recovery_continue.click()
        past_setup(qapp, made)
        wait_until(qapp, lambda: made.session.preferences is not None)
        yield made
    finally:
        with contextlib.suppress(RuntimeError):
            made.session.client.reset()
        made.hide()
        qapp.processEvents()
        server.stop()


def clay_at_1024_by_640_large(qapp: QApplication, window: NativeWindow) -> None:
    """Clay on the week page, Large text, the window at the smallest size the app is meant for, with
    homework left over from last week so the planning strip above the deck takes its room, as it does
    for a student with work behind."""
    session = window.session
    monday = datetime.fromisoformat(session.week_start)
    due = (monday - timedelta(days=3)).strftime("%Y-%m-%dT23:59")
    session.add_homework({"id": "left", "title": "Lab report", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    window.session.look = window._look
    window._carry_look()
    window._layout = sanitize_layout({"main": "clay", "day": "one", "options": {}})
    window._apply_appearance()
    window._on_week()
    window.resize(1024, 640)
    window.show()
    for _ in range(20):
        qapp.processEvents()
    assert window.unfinished_panel.isVisibleTo(window), "the planning strip above the deck is not up"


def test_clays_front_card_is_whole_on_screen_at_1024_by_640_large_text(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The card in front is the deck's one thing to read. Mutation that turns this red: the row asks
    for 340 pixels of height at any text size (the old LEAST), so the page scrolls and the card's
    bottom is cut by the page's viewport."""
    clay_at_1024_by_640_large(qapp, window)
    page = window.findChild(QScrollArea, "clayScroll")
    assert page is not None and page.isVisible()
    row = window.planner.currentWidget().row
    card = slots(row.width(), row.height(), row.front, row.scale, wide=row._open)[row.front]
    top_left = row.mapTo(page.viewport(), card.toRect().topLeft())
    bottom = row.mapTo(page.viewport(), card.toRect().bottomLeft()).y()
    assert top_left.y() >= 0, "the card's top is above the page's viewport"
    assert bottom <= page.viewport().height(), (bottom, page.viewport().height())


def test_clay_front_hour_blocks_are_whole_or_scrolled_past_at_1024_by_640_large(
    qapp: QApplication, window: NativeWindow
) -> None:
    clay_at_1024_by_640_large(qapp, window)
    session = window.session
    session.add_block(
        {
            "id": "edge-class",
            "title": "Morning class",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 90,
            "days": list(range(7)),
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    window._on_week()
    row = window.planner.currentWidget().row
    page = window.findChild(QScrollArea, "clayScroll")
    assert page is not None, "the Clay page has its visible viewport"
    for wide in (False, True):
        session.set_view("day" if wide else "week")
        window._on_week()
        for front in range(7):
            row._go(front, "jump", force=True)
            qapp.processEvents()
            scroll = row.hours
            assert scroll is not None, "the front Clay card has an hour list"
            canvas = scroll.canvas
            viewport = scroll.viewport()
            matches = [
                (drawn, rect)
                for track in canvas.tracks
                for drawn, rect in canvas.drawn(track)
                if drawn.block_id == "edge-class"
            ]
            assert matches, f"the front Clay hour list contains Morning class for day {front}"
            for drawn, rect in matches:
                for visible in (viewport, page.viewport()):
                    top = canvas.mapTo(visible, rect.toRect().topLeft()).y()
                    bottom = canvas.mapTo(visible, rect.toRect().bottomLeft()).y()
                    whole = top >= 0 and bottom <= visible.height()
                    past = bottom <= 0 or top >= visible.height()
                    assert whole or past, (
                        f"{drawn.title} on day {drawn.span.day} is cut by the visible front hour list "
                        f"at 1024x640 Large: y={top}..{bottom}, viewport={visible.height()}"
                    )


def test_clay_at_1024_by_640_large_text_keeps_the_window_at_1024_by_640(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Passes before and after the row's minimum changed: the window stays put in this account. It
    guards against a Clay change that makes the window grow past the smallest size."""
    clay_at_1024_by_640_large(qapp, window)
    assert (window.width(), window.height()) == (1024, 640)


def test_window_minimum_ignores_the_hidden_sign_in_page(qapp: QApplication, window: NativeWindow) -> None:
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    window.session.look = window._look
    window._carry_look()
    window._carried = ("large", False)
    window._apply_appearance()
    window.resize(1024, 640)
    qapp.processEvents()
    assert window.minimumSizeHint().width() <= 1024, "the hidden sign-in page does not raise the window width"
    assert window.minimumSizeHint().height() <= 640, (
        "the hidden sign-in page does not raise the window minimum"
    )
    assert (window.width(), window.height()) == (1024, 640), (
        "the window stays at 1024x640 with sign-in hidden"
    )


@pytest.mark.parametrize(
    ("mode", "button_name"),
    [("sign in", "signIn"), ("create", "createAccount"), ("reset", "recoverAccount")],
)
def test_auth_page_fits_1024_by_640_at_large_text(
    qapp: QApplication, window: NativeWindow, mode: str, button_name: str
) -> None:
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    window.session.look = window._look
    window._carry_look()
    window._carried = ("large", False)
    window._apply_appearance()
    window._entry_mode = mode
    auth_page = window.findChild(QWidget, "authPage")
    assert auth_page is not None, "the auth page is present"
    window._stack.setCurrentWidget(auth_page)
    window._sync_auth_mode()
    window.resize(1024, 640)
    qapp.processEvents()
    assert window.minimumSizeHint().height() <= 640, f"{mode} allows a 640 px window"
    assert (window.width(), window.height()) == (1024, 640), f"{mode} keeps the requested window size"
    scroll = window.findChild(QScrollArea, "authScroll")
    card = window._auth_card
    assert scroll is not None and card is not None, f"{mode} page and card are present"
    assert card.mapTo(scroll.widget(), card.rect().bottomLeft()).y() <= scroll.widget().height(), (
        f"{mode} card stays whole in the scroll content"
    )
    if mode == "sign in":
        scroll.ensureWidgetVisible(card, 0, 0)
        qapp.processEvents()
        top = card.mapTo(scroll.viewport(), card.rect().topLeft()).y()
        bottom = card.mapTo(scroll.viewport(), card.rect().bottomLeft()).y()
        assert top >= 0 and bottom <= scroll.viewport().height(), "the sign-in card is wholly visible"
    button = window.findChild(QPushButton, button_name)
    assert button is not None and button.isVisibleTo(card), f"{mode} action stays available"
    scroll.ensureWidgetVisible(button)
    qapp.processEvents()
    top = button.mapTo(scroll.viewport(), button.rect().topLeft()).y()
    bottom = button.mapTo(scroll.viewport(), button.rect().bottomLeft()).y()
    assert top >= 0 and bottom <= scroll.viewport().height(), f"{mode} action can be reached by scrolling"
    assert all(field.height() >= 48 for field in card.findChildren(QLineEdit) if field.isVisible()), (
        f"{mode} keeps every visible field at least 48 px tall"
    )
    assert button.height() >= 48, f"{mode} action stays at least 48 px tall"


@pytest.mark.parametrize("mode", ["sign in", "create", "reset"])
def test_auth_spacing_is_unchanged_at_1280_by_800_large_text(
    qapp: QApplication, window: NativeWindow, mode: str
) -> None:
    from desktop.native.look import text_scale
    from desktop.native.window import SPACING

    window._look = sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    window.session.look = window._look
    window._carry_look()
    window._carried = ("large", False)
    window._apply_appearance()
    window._entry_mode = mode
    auth_page = window.findChild(QWidget, "authPage")
    assert auth_page is not None, "the auth page is present"
    window._stack.setCurrentWidget(auth_page)
    window._sync_auth_mode()
    scale = text_scale(window._worn_look())
    assert scale > 1, "the entry page uses Large text"
    expected = SPACING[1] if mode == "reset" else SPACING[3]
    if mode == "create" and scale > 1:
        expected = SPACING[2]
    window.resize(1280, 800)
    qapp.processEvents()
    scroll = window.findChild(QScrollArea, "authScroll")
    assert scroll is not None
    outer = scroll.widget().layout()
    reference_widget = QWidget(scroll.widget())
    reference = QVBoxLayout(reference_widget)
    assert outer.spacing() == reference.spacing(), f"{mode} outer spacing is unchanged"
    assert outer.contentsMargins() == reference.contentsMargins(), f"{mode} outer margins are unchanged"
    assert window._auth_card.layout().spacing() == expected, f"{mode} card spacing is unchanged"
    assert window._auth_card.layout().contentsMargins().left() == 0
