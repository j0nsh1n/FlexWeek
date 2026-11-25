# ruff: noqa: F811
"""Report a problem in Settings > Computer opens the maintainer's form with this version and computer
filled in, and shows nothing while no form link is set."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native import feedback  # noqa: E402
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


def test_the_shipped_form_link_is_one_pre_filled_google_form_on_the_computer_and_the_phone() -> None:
    """Jonathan's form (2026-11-24). Its pre-filled link carries each sample answer once, which is what
    the computer and the phone swap for the real version and device; both use the same link."""
    import re
    from pathlib import Path
    from urllib.parse import parse_qsl, urlsplit

    link = feedback.FORM_LINK
    parts = urlsplit(link)
    assert (parts.scheme, parts.hostname) == ("https", "docs.google.com")
    assert re.fullmatch(r"/forms/d/e/[A-Za-z0-9_-]+/viewform", parts.path)
    answers = parse_qsl(parts.query)
    assert answers[0] == ("usp", "pp_url")
    values = [value for _key, value in answers[1:]]
    assert sorted(values) == sorted([feedback.SAMPLE_VERSION, feedback.SAMPLE_DEVICE])
    assert all(re.fullmatch(r"entry\.\d+", key) for key, _value in answers[1:])

    root = Path(__file__).resolve().parents[3]
    kotlin = (root / "android/app/src/main/java/com/flexweek/app/ui/reminders/FeedbackForm.kt").read_text()
    found = re.search(r"const val FEEDBACK_FORM_LINK =((?:\s*\"[^\"]*\"\s*\+?)+)", kotlin)
    assert found is not None
    assert "".join(re.findall(r"\"([^\"]*)\"", found.group(1))) == link
    samples = {"SAMPLE_VERSION": feedback.SAMPLE_VERSION, "SAMPLE_DEVICE": feedback.SAMPLE_DEVICE}
    for name, value in samples.items():
        assert f'const val {name} = "{value}"' in kotlin


def test_no_form_link_shows_no_button(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(feedback, "FORM_LINK", "")
    root = open_computer_section(qapp, window)
    assert panel(window).state["feedbackAvailable"] is False
    assert bool(named(root, "reportProblemRow")[0].property("visible")) is False


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
