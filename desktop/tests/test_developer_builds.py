# ruff: noqa: F811
"""Get developer builds: the switch, the `dev` pre-release check, and the version label."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from desktop.native.update import sanitize_updates

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native import updater as updater_module  # noqa: E402
from desktop.native.updater import Updater  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.test_material_window import qapp, window  # noqa: E402, F401

KEPT: list[object] = []
TARBALL = "FlexWeek-Linux-x86_64.tar.gz"


def test_the_switch_is_off_by_default_and_survives_a_save() -> None:
    assert sanitize_updates({})["developer_builds"] is False
    assert sanitize_updates({"developer_builds": True})["developer_builds"] is True
    assert sanitize_updates({"developer_builds": "yes"})["developer_builds"] is False


def _dev_release(version: str) -> dict:
    """The `dev` pre-release as GitHub returns it: the tag is always `dev`, the version is in the title."""
    return {**_release("dev", prerelease=True), "name": f"Developer build {version}"}


def _release(tag: str, *, prerelease: bool = False) -> dict:
    return {
        "tag_name": tag,
        "draft": False,
        "prerelease": prerelease,
        "assets": [
            {
                "name": TARBALL,
                "browser_download_url": f"https://example.invalid/{tag}/{TARBALL}",
            },
            {
                "name": TARBALL + ".sha256",
                "browser_download_url": f"https://example.invalid/{tag}/{TARBALL}.sha256",
            },
        ],
    }


class GitHub(BaseHTTPRequestHandler):
    """Latest and `dev` answers, plus the release-page fallback the updater already uses."""

    latest_status = 200
    dev_status = 200
    latest_body = b"{}"
    dev_body = b"{}"
    seen: list[str] = []

    def do_GET(self) -> None:  # noqa: N802
        GitHub.seen.append(self.path)
        if self.path == "/api":
            self.send_response(self.latest_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(self.latest_body)
            return
        if self.path == "/dev":
            self.send_response(self.dev_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(self.dev_body)
            return
        self.send_response(302)
        self.send_header("Location", "https://github.com/j0nsh1n/FlexWeek/releases/tag/v1.2.0")
        self.end_headers()

    def log_message(self, *_args: object) -> None:
        return


@pytest.fixture()
def github(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    GitHub.seen = []
    GitHub.latest_status = 200
    GitHub.dev_status = 200
    GitHub.latest_body = json.dumps(_release("v1.2.0")).encode()
    GitHub.dev_body = json.dumps(_dev_release("1.2.0.202611040300")).encode()
    server = ThreadingHTTPServer(("127.0.0.1", 0), GitHub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setattr(updater_module, "RELEASES_URL", origin + "/api")
    monkeypatch.setattr(updater_module, "DEV_URL", origin + "/dev")
    monkeypatch.setattr(updater_module, "RELEASE_PAGE", origin + "/page")
    monkeypatch.setattr(updater_module, "CHECK_TIMEOUT_MS", 300)
    yield origin
    server.shutdown()


def made() -> Updater:
    updater = Updater()
    updater.kind = "tarball"
    KEPT.append(updater)
    return updater


def outcome(
    qapp: QApplication, updater: Updater, timeout: float = 5.0, *, developer: bool = False
) -> tuple[str, object]:
    heard: list[tuple[str, object]] = []
    updater.found.connect(lambda update: heard.append(("found", update)))
    updater.none_found.connect(lambda: heard.append(("none", None)))
    updater.unreachable.connect(lambda why: heard.append(("unreachable", why)))
    updater.failed.connect(lambda why: heard.append(("failed", why)))
    updater.check(developer=developer)
    wait_until(qapp, lambda: bool(heard), timeout)
    return heard[0]


def wait_until(qapp: QApplication, predicate: Callable[[], bool], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("the check never finished")


def test_with_the_switch_off_the_dev_build_is_never_asked_for(qapp: QApplication, github: str) -> None:
    updater = made()
    outcome(qapp, updater, developer=False)
    assert "/dev" not in GitHub.seen


def test_a_newer_dev_build_is_offered_with_the_switch_on(qapp: QApplication, github: str) -> None:
    updater = made()
    kind, update = outcome(qapp, updater, developer=True)
    assert kind == "found"
    assert isinstance(update, dict)
    assert update["version"] == "1.2.0.202611040300"
    assert update["asset"] == TARBALL


def test_a_newer_official_release_beats_an_older_dev_build(
    qapp: QApplication, github: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    GitHub.latest_body = json.dumps(_release("v1.2.1")).encode()
    GitHub.dev_body = json.dumps(_dev_release("1.2.0.202611050300")).encode()
    real = updater_module.available
    monkeypatch.setattr(
        updater_module,
        "available",
        lambda release, kind, current="1.2.0.202611040300": real(release, kind, current),
    )
    updater = made()
    kind, update = outcome(qapp, updater, developer=True)
    assert kind == "found"
    assert isinstance(update, dict)
    assert update["version"] == "1.2.1"


def test_a_failed_dev_request_falls_back_to_the_release_answer(qapp: QApplication, github: str) -> None:
    GitHub.latest_body = json.dumps(_release("v99.0.0")).encode()
    GitHub.dev_status = 500
    updater = made()
    kind, update = outcome(qapp, updater, developer=True)
    assert kind == "found"
    assert isinstance(update, dict)
    assert update["version"] == "99.0.0"


def test_the_material_switch_saves_the_setting(qapp: QApplication, window: NativeWindow) -> None:
    from desktop.tests.test_layouts_window import look_file, wait_until
    from desktop.tests.test_material_settings import (
        _click,
        _named,
        _open_settings,
        _reset,
    )
    from desktop.tests.test_material_window import _visuals

    root = _open_settings(qapp, window, "computer")
    try:
        row = _named(root, "developerBuildsRow")[0]
        switch = next(item for item in _visuals(row) if str(item.objectName()) == "developerBuilds")
        _click(qapp, window, switch)
        wait_until(qapp, lambda: window._updates.get("developer_builds") is True)
        saved = json.loads(look_file().read_text(encoding="utf-8"))
        assert saved["updates"]["developer_builds"] is True
    finally:
        _reset(window)


def test_a_dev_build_says_developer_build_in_settings(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from desktop.native.material import bridge_settings
    from desktop.native.version import VERSION
    from desktop.tests.test_material_settings import (
        _named,
        _open_settings,
        _panel,
        _pump,
        _reset,
        _texts,
    )

    root = _open_settings(qapp, window, "computer")
    try:
        panel = _panel(window)
        assert panel.state["version"] == f"FlexWeek {VERSION}"
        assert "developer build" not in panel.state["version"]
        monkeypatch.setattr(bridge_settings, "CHANNEL", "dev")
        panel._publish()
        _pump(qapp)
        assert panel.state["version"] == f"FlexWeek {VERSION} (developer build)"
        words = " ".join(str(item.property("text") or "") for item in _texts(_named(root, "row_updates")[0]))
        assert "developer build" in words
    finally:
        _reset(window)


def test_a_dev_release_without_a_version_in_its_title_is_not_offered(qapp: QApplication, github: str) -> None:
    GitHub.dev_body = json.dumps({**_dev_release("1.2.0.202611040300"), "name": "Developer build"}).encode()
    updater = made()
    kind, _update = outcome(qapp, updater, developer=True)
    assert kind == "none"


def test_a_dev_title_may_carry_its_commit_after_the_number(qapp: QApplication, github: str) -> None:
    """Developer builds will name their commit, "Developer build 1.2.0.202611040300 (4b3e1cd)"; the number
    still decides what is newer. Anything else after the number is not a developer build title."""
    GitHub.dev_body = json.dumps(
        {**_dev_release("1.2.0.202611040300"), "name": "Developer build 1.2.0.202611040300 (4b3e1cd)"}
    ).encode()
    kind, update = outcome(qapp, made(), developer=True)
    assert kind == "found"
    assert isinstance(update, dict) and update["version"] == "1.2.0.202611040300"
    for name in (
        "Developer build 1.2.0.202611040300 (not a commit)",
        "Developer build 1.2.0.202611040300 4b3e1cd",
    ):
        GitHub.dev_body = json.dumps({**_dev_release("1.2.0.202611040300"), "name": name}).encode()
        kind, _update = outcome(qapp, made(), developer=True)
        assert kind == "none", name


def test_widgets_settings_has_the_same_switch(qapp: QApplication, window: NativeWindow) -> None:
    """The switch was only in Material's Settings; Widgets This computer shows the same saved setting."""
    from PySide6.QtWidgets import QWidget

    from desktop.tests.test_layouts_window import look_file

    before = dict(window._updates)
    try:
        window._surface = "widgets"
        window._material_gave_up = False
        window._on_week()
        window._updates["developer_builds"] = True
        window._save_look()
        assert json.loads(look_file().read_text(encoding="utf-8"))["updates"]["developer_builds"] is True
        window._open_settings()
        switch = window._settings.findChild(QWidget, "prefDeveloperBuilds")
        assert switch is not None and switch.isChecked() is True
        switch.click()
        qapp.processEvents()
        assert window._updates["developer_builds"] is False
        assert json.loads(look_file().read_text(encoding="utf-8"))["updates"]["developer_builds"] is False
        window._close_settings()
        window._updates["developer_builds"] = True  # as Material's switch would
        window._open_settings()
        assert window._settings.findChild(QWidget, "prefDeveloperBuilds").isChecked() is True
    finally:
        window._close_settings()
        window._updates.clear()
        window._updates.update(before)
        window._save_look()
