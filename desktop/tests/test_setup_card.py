"""First-week setup is three skippable steps, not a blocked wizard."""

from __future__ import annotations

import importlib.util
import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QPoint, QStandardPaths, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QWidget

    from desktop.native.look import pack_stylesheet
    from desktop.native.settings import SetupCard
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-setup-test"])
    yield application


def test_skipping_sport_still_keeps_school(qapp: QApplication) -> None:
    card = SetupCard()
    found: list[dict] = []
    card.finished.connect(found.append)
    card.findChild(QPushButton, "setupNext").click()
    card.findChild(QPushButton, "setupSkip").click()
    card.findChild(QPushButton, "setupNext").click()
    assert found
    assert "school" in found[0]
    assert "sport" not in found[0]
    assert "homework" in found[0]


def test_the_card_is_opaque_so_the_week_does_not_show_through_it(qapp: QApplication) -> None:
    """It is positioned over the calendar rather than placed in a layout. A QWidget honours a
    stylesheet background but a subclass of one does not unless it is told to, so the card came up
    transparent and the day headings and hour lines were drawn through its own text."""
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QWidget

    from desktop.native.look import pack_stylesheet, resolved_palette

    page = QWidget()
    page.resize(700, 500)
    page.setStyleSheet(pack_stylesheet("light-frost", False, None, "default"))
    card = SetupCard(page)
    card.setFixedWidth(420)
    card.move(20, 20)
    card.show()
    page.show()
    qapp.processEvents()
    card.adjustSize()
    qapp.processEvents()
    # Something loud behind it: if any of it survives inside the card, the card is see-through.
    behind = QWidget(page)
    behind.setGeometry(card.geometry())
    behind.setStyleSheet("background: #ff00ff;")
    behind.lower()
    qapp.processEvents()
    image = page.grab().toImage()
    panel = QColor(resolved_palette("light-frost", False, None, "default")["panel"])
    middle = image.pixelColor(card.x() + card.width() // 2, card.y() + card.height() // 2)
    assert middle != QColor("#ff00ff"), "the week shows through the first-week card"
    assert middle == panel, f"the card is not painted on its own panel: {middle.name()}"
    page.close()


def _sport_step(card: SetupCard) -> QLineEdit:
    card.findChild(QPushButton, "setupNext").click()
    return card.sport_title


def test_typing_at_the_left_of_the_sport_name_replaces_nothing(qapp: QApplication) -> None:
    """The field used to ship with the letters Soccer already in it. A click at the left then
    typing Socc produced SoccSoccer."""
    card = SetupCard()
    card.show()
    qapp.processEvents()
    field = _sport_step(card)
    assert field.text() == ""
    assert field.placeholderText() == "Soccer, band, karate…"
    QTest.mouseClick(field, Qt.MouseButton.LeftButton, pos=QPoint(3, max(field.height() // 2, 1)))
    QTest.keyClicks(field, "Socc")
    assert field.text() == "Socc"
    card.close()


def test_a_blank_sport_name_is_saved_as_sport_or_club(qapp: QApplication) -> None:
    card = SetupCard()
    found: list[dict] = []
    card.finished.connect(found.append)
    card.findChild(QPushButton, "setupNext").click()
    card.findChild(QPushButton, "setupNext").click()
    card.findChild(QPushButton, "setupNext").click()
    assert found[0]["sport"][0] == "Sport or club"


def test_typing_in_a_time_field_replaces_the_default(qapp: QApplication) -> None:
    card = SetupCard()
    card.show()
    qapp.processEvents()
    field = card.school_start
    QTest.mouseClick(field, Qt.MouseButton.LeftButton, pos=QPoint(3, max(field.height() // 2, 1)))
    qapp.processEvents()
    QTest.keyClicks(field, "07:30")
    assert field.text() == "07:30"
    card.close()


def test_tabbing_into_a_time_field_selects_the_default(qapp: QApplication) -> None:
    card = SetupCard()
    card.show()
    qapp.processEvents()
    card.school_end.setFocus()
    qapp.processEvents()
    card.school_start.setFocus(Qt.FocusReason.TabFocusReason)
    qapp.processEvents()
    assert card.school_start.selectedText() == card.school_start.text() == "08:00"
    card.close()


def test_a_second_click_in_a_time_field_places_the_caret(qapp: QApplication) -> None:
    """Only the click that brings the focus selects the default. After that a click puts the caret
    where it lands, so "08:00" can be corrected to "08:30" without retyping it."""
    card = SetupCard()
    card.show()
    qapp.processEvents()
    field = card.school_start
    middle = QPoint(3, max(field.height() // 2, 1))
    QTest.mouseClick(field, Qt.MouseButton.LeftButton, pos=middle)
    qapp.processEvents()
    assert field.selectedText() == "08:00"
    QTest.mouseClick(field, Qt.MouseButton.LeftButton, pos=middle)
    qapp.processEvents()
    assert field.selectedText() == ""
    field.setCursorPosition(4)
    QTest.keyClick(field, Qt.Key.Key_Backspace)
    QTest.keyClicks(field, "3")
    assert field.text() == "08:30"
    card.close()


def test_the_window_uses_the_same_blank_sport_name(qapp: QApplication, tmp_path: Path) -> None:
    QStandardPaths.setTestModeEnabled(True)
    server = LocalServer(Path(tmp_path) / "setup.db")
    server.start()
    window = NativeWindow(server.origin)
    window.username.setText("setup_sport")
    window.password.setText("a-long-test-password")
    window.findChild(QPushButton, "createAccount").click()
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        qapp.processEvents()
        if window._stack.currentWidget().objectName() == "recoveryPage":
            break
        time.sleep(0.02)
    window.recovery_ack.setChecked(True)
    window.recovery_continue.click()
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        qapp.processEvents()
        if window._stack.currentWidget().objectName() == "weekPage":
            break
        time.sleep(0.02)
    window._apply_setup({"sport": ("", "15:30", "17:00")})
    titles = [block["title"] for block in window.session.blocks]
    assert "Sport or club" in titles
    window.session.client.reset()
    qapp.processEvents()
    server.stop()
    window.close()


def test_setup_labels_sit_beside_their_fields_at_every_text_size(qapp: QApplication) -> None:
    out = Path("/tmp/ia141-grok")
    out.mkdir(parents=True, exist_ok=True)
    for size in ("small", "normal", "large"):
        page = QWidget()
        page.resize(700, 500)
        page.setStyleSheet(pack_stylesheet("light-frost", False, {"knobs": {"text": size}}, "default"))
        card = SetupCard(page)
        card.setFixedWidth(420)
        card.move(20, 20)
        card.show()
        page.show()
        qapp.processEvents()
        card.adjustSize()
        qapp.processEvents()
        card.grab().save(str(out / f"setup-school-{size}.png"))
        card.findChild(QPushButton, "setupNext").click()
        qapp.processEvents()
        card.adjustSize()
        qapp.processEvents()
        for field in (card.sport_title, card.sport_start, card.sport_end):
            pair = field.parentWidget()
            assert pair is not None
            label = pair.findChild(QLabel)
            assert label is not None
            label_mid = label.mapTo(card.sport_row, QPoint(0, label.height() // 2)).y()
            field_mid = field.mapTo(card.sport_row, QPoint(0, field.height() // 2)).y()
            assert abs(label_mid - field_mid) <= 3, (
                f"{size} {label.text()}: label mid {label_mid} vs field mid {field_mid}"
            )
        card.grab().save(str(out / f"setup-sport-{size}.png"))
        page.close()


def test_a_time_the_student_typed_is_not_selected_again(qapp: QApplication) -> None:
    """Coming back to a field that holds the student's own time is editing it, not replacing a
    default, so the click places the caret."""
    card = SetupCard()
    card.show()
    qapp.processEvents()
    field = card.school_start
    edge = QPoint(3, max(field.height() // 2, 1))
    QTest.mouseClick(field, Qt.MouseButton.LeftButton, pos=edge)
    QTest.keyClicks(field, "07:30")
    card.school_end.setFocus()
    qapp.processEvents()
    QTest.mouseClick(field, Qt.MouseButton.LeftButton, pos=edge)
    qapp.processEvents()
    assert field.text() == "07:30"
    assert field.selectedText() == ""
    card.close()
