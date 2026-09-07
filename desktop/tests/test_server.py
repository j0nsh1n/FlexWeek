"""The bundled server: a real port, the real app, started and stopped."""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

import pytest

from desktop.server import LocalServer


@pytest.fixture
def server(tmp_path: Path):
    running = LocalServer(tmp_path / "flexweek.db")
    running.start()
    yield running
    running.stop()


def test_start_returns_the_origin_it_is_actually_serving(tmp_path: Path) -> None:
    running = LocalServer(tmp_path / "flexweek.db")
    try:
        returned = running.start()
        assert returned == f"http://127.0.0.1:{running.port}"
        with urllib.request.urlopen(f"{returned}/api/health", timeout=10) as response:
            assert response.status == 200
    finally:
        running.stop()


def test_it_serves_the_api_and_the_frontend(server: LocalServer) -> None:
    with urllib.request.urlopen(f"{server.origin}/api/health", timeout=10) as response:
        assert response.status == 200
    with urllib.request.urlopen(f"{server.origin}/", timeout=10) as response:
        assert response.status == 200
        assert b"FlexWeek" in response.read()


def test_the_origin_check_still_applies_to_the_bundled_server(server: LocalServer) -> None:
    # A write claiming a different origin must be refused, exactly as when hosted.
    request = urllib.request.Request(
        f"{server.origin}/api/auth/login",
        data=b'{"username":"someone","password":"correct-horse-battery"}',
        headers={
            "Content-Type": "application/json",
            "X-FlexWeek-Request": "1",
            "Origin": "https://evil.example",
        },
    )
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(request, timeout=10)
    assert caught.value.code == 403


def test_the_database_is_created_where_it_was_asked_for(tmp_path: Path) -> None:
    database = tmp_path / "nested" / "flexweek.db"
    database.parent.mkdir()
    running = LocalServer(database)
    try:
        running.start()
        assert database.exists()
    finally:
        running.stop()


def test_stop_ends_the_serving_thread_and_the_port(tmp_path: Path) -> None:
    running = LocalServer(tmp_path / "a.db")
    running.start()
    port = running.port
    assert running.is_running
    running.stop()
    assert not running.is_running
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3)
