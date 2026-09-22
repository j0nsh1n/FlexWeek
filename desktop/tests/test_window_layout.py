"""The week page has to fit a laptop and give the calendar the room.

Every behavioural test passed while the window demanded over 2,300 pixels of width and the calendar
got five rows, because no test looked at geometry. The numbers here come from the requirement: a
1366 by 768 laptop screen, and a calendar that is at least half of the window it is the point of.
"""

from __future__ import annotations

import contextlib
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
    from PySide6.QtCore import QRect, QStandardPaths
    from PySide6.QtWidgets import QApplication, QPushButton, QWidget

    from desktop.native.widgets import FlowLayout
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer
    from desktop.tests.logic_support import past_setup

LAPTOP = (1366, 768)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-layout-test"])
    yield application


def wait_until(qapp: QApplication, predicate, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was still false")


@pytest.fixture()
def week_page(qapp: QApplication, tmp_path: Path) -> Iterator[NativeWindow]:
    server = LocalServer(tmp_path / "flexweek.db")
    server.start()
    window = NativeWindow(server.origin)
    window.username.setText("layout_student")
    window.password.setText("a-long-test-password")
    window.findChild(QPushButton, "createAccount").click()
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "recoveryPage")
    window.recovery_ack.setChecked(True)
    window.recovery_continue.click()
    past_setup(qapp, window)
    yield window
    with contextlib.suppress(RuntimeError):
        window.session.client.reset()
    qapp.processEvents()
    server.stop()


def test_the_week_page_fits_a_laptop_screen(qapp: QApplication, week_page: NativeWindow) -> None:
    smallest = week_page.minimumSizeHint()
    assert smallest.width() <= LAPTOP[0], f"the window cannot be narrower than {smallest.width()} pixels"
    assert smallest.height() <= LAPTOP[1], f"the window cannot be shorter than {smallest.height()} pixels"
    week_page.resize(1280, 760)
    week_page.show()
    qapp.processEvents()
    assert (week_page.width(), week_page.height()) == (1280, 760)


def test_the_calendar_gets_at_least_half_of_the_window(qapp: QApplication, week_page: NativeWindow) -> None:
    week_page.resize(1280, 820)
    week_page.show()
    qapp.processEvents()
    share = week_page.week_table.height() / week_page.height()
    assert share >= 0.5, f"the calendar has {week_page.week_table.height()} of {week_page.height()} pixels"


def test_a_flow_layout_wraps_instead_of_demanding_the_width(qapp: QApplication) -> None:
    host = QWidget()
    flow = FlowLayout(host)
    buttons = [QPushButton(f"Action number {index}") for index in range(20)]
    for button in buttons:
        flow.addWidget(button)
    widest = max(button.sizeHint().width() for button in buttons)
    margins = flow.contentsMargins()
    assert flow.minimumSize().width() == widest + margins.left() + margins.right()
    assert flow.heightForWidth(400) > flow.heightForWidth(4000), "a narrow row must wrap onto more rows"
    flow.setGeometry(QRect(0, 0, 400, flow.heightForWidth(400)))
    for button in buttons:
        assert button.geometry().right() <= 400, f"{button.text()} overflows the row"
    assert len({button.geometry().top() for button in buttons}) > 1
