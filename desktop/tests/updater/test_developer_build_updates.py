# ruff: noqa: F811
"""Get developer builds: when the update check asks for the `dev` pre-release, and which title it reads
a version from. The checks run against a small local web server that answers like GitHub."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native import updater as updater_module
from desktop.native.updater import Updater
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

KEPT: list[object] = []
TARBALL = "FlexWeek-Linux-x86_64.tar.gz"


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


def _dev_release(version: str) -> dict:
    """The `dev` pre-release as GitHub returns it: the tag is always `dev`, the version is in the title."""
    return {**_release("dev", prerelease=True), "name": f"Developer build {version}"}


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


def installed_as(monkeypatch: pytest.MonkeyPatch, current: str = "1.2.0.202611040300") -> None:
    """Pretend this copy is an older developer build, so a bump of the real VERSION cannot change what
    these checks offer."""
    real = updater_module.available
    monkeypatch.setattr(
        updater_module,
        "available",
        lambda release, kind, current=current: real(release, kind, current),
    )


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
    wait_until(qapp, lambda: bool(heard), timeout, what="the update check never finished")
    return heard[0]


def test_with_the_switch_off_the_dev_build_is_never_asked_for(qapp: QApplication, github: str) -> None:
    updater = made()
    outcome(qapp, updater, developer=False)
    assert "/dev" not in GitHub.seen


def test_a_newer_dev_build_is_offered_with_the_switch_on(
    qapp: QApplication,
    github: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed_as(monkeypatch, "1.2.0.202611030300")
    updater = made()
    kind, update = outcome(qapp, updater, developer=True)
    assert kind == "found"
    assert isinstance(update, dict)
    assert update["version"] == "1.2.0.202611040300"
    assert update["asset"] == TARBALL


def test_a_newer_official_release_beats_an_older_dev_build(
    qapp: QApplication,
    github: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    GitHub.latest_body = json.dumps(_release("v1.2.1")).encode()
    GitHub.dev_body = json.dumps(_dev_release("1.2.0.202611050300")).encode()
    installed_as(monkeypatch)
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


def test_a_dev_release_without_a_version_in_its_title_is_not_offered(
    qapp: QApplication,
    github: str,
) -> None:
    GitHub.dev_body = json.dumps({**_dev_release("1.2.0.202611040300"), "name": "Developer build"}).encode()
    updater = made()
    kind, _update = outcome(qapp, updater, developer=True)
    assert kind == "none"


def test_a_dev_title_may_carry_its_commit_after_the_number(
    qapp: QApplication,
    github: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Developer builds name their commit, "Developer build 1.2.0.202611040300 (4b3e1cd)"; the number
    still decides what is newer. Anything else after the number is not a developer build title."""
    installed_as(monkeypatch, "1.2.0.202611030300")
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


@pytest.mark.parametrize("kind", ["windows", "appimage"])
def test_a_saved_switch_off_the_linux_tarball_never_asks_for_the_dev_build(
    qapp: QApplication, github: str, kind: str
) -> None:
    """The setting can be saved as on from a tarball copy; a Windows or AppImage install has no developer
    build to fetch, so it only gets the official answer."""
    updater = made()
    updater.kind = kind
    outcome(qapp, updater, developer=True)
    assert "/dev" not in GitHub.seen
