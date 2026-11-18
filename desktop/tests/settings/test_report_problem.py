# ruff: noqa: F811
"""Report a problem in Settings: both designs open the maintainer's form with this version and computer
filled in, and show nothing while no form link is set."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop.native import feedback  # noqa: E402
from desktop.native.settings import SettingsPage  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.updater.test_get_developer_builds_switch import (  # noqa: E402
    click,
    named,
    open_computer_section,
    panel,
)
from desktop.tests.window_support import qapp  # noqa: E402, F401

LINK = (
    "https://docs.google.com/forms/d/e/FORM/viewform?usp=pp_url&entry.111=1.4.0&entry.222=test&entry.333=keep"
)
FILLED = (
    "https://docs.google.com/forms/d/e/FORM/viewform?usp=pp_url"
    "&entry.111=1.4.1&entry.222=Linux+6.8+%28x86_64%29&entry.333=keep"
)


class Opened:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def openUrl(self, url) -> bool:  # noqa: N802 - the Qt name it stands in for
        self.urls.append(url.toString())
        return True


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> Opened:
    seen = Opened()
    monkeypatch.setattr(feedback, "QDesktopServices", seen)
    return seen


def test_the_form_link_gets_this_version_and_computer() -> None:
    # The third answer is not a sample, so it stays as it is.
    assert feedback.form_url(LINK, "1.4.1", "Linux 6.8 (x86_64)") == FILLED


def test_no_form_link_shows_no_button_in_either_design(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(feedback, "FORM_LINK", "")
    page = SettingsPage(
        window, window.session.preferences or {}, window._look, window.session.reminder_limits
    )
    assert page.findChild(QPushButton, "prefsReportProblem") is None
    root = open_computer_section(qapp, window)
    assert panel(window).state["feedbackAvailable"] is False
    assert bool(named(root, "reportProblemRow")[0].property("visible")) is False


def test_widgets_settings_opens_the_filled_form(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, opened: Opened
) -> None:
    monkeypatch.setattr(feedback, "FORM_LINK", LINK)
    monkeypatch.setattr(feedback, "VERSION", "1.4.1")
    monkeypatch.setattr(feedback, "device_text", lambda: "Linux 6.8 (x86_64)")
    page = SettingsPage(
        window, window.session.preferences or {}, window._look, window.session.reminder_limits
    )
    page.findChild(QPushButton, "prefsReportProblem").click()
    assert opened.urls == [FILLED]


def test_material_settings_opens_the_filled_form(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, opened: Opened
) -> None:
    monkeypatch.setattr(feedback, "FORM_LINK", LINK)
    monkeypatch.setattr(feedback, "VERSION", "1.4.1")
    monkeypatch.setattr(feedback, "device_text", lambda: "Linux 6.8 (x86_64)")
    root = open_computer_section(qapp, window)
    panel(window)._publish()
    qapp.processEvents()
    row = named(root, "reportProblemRow")[0]
    assert bool(row.property("visible")) is True
    click(qapp, window, row)
    assert opened.urls == [FILLED]
