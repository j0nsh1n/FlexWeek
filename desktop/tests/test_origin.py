"""Origin rules for the desktop shell. Pure logic; no Qt import, so these run
anywhere the web app's test suite runs."""

from __future__ import annotations

import pytest

from desktop.origin import DEFAULT_ORIGIN, is_same_origin, origin_key, resolve_origin, validate_origin


def test_default_origin_when_unset() -> None:
    assert resolve_origin({}) == DEFAULT_ORIGIN


def test_desktop_origin_wins_over_web_origin() -> None:
    env = {"FLEXWEEK_ORIGIN": "https://web.example", "FLEXWEEK_DESKTOP_ORIGIN": "https://app.example"}
    assert resolve_origin(env) == "https://app.example"


def test_blank_env_falls_through_to_default() -> None:
    assert resolve_origin({"FLEXWEEK_DESKTOP_ORIGIN": "   "}) == DEFAULT_ORIGIN


def test_trailing_slash_is_stripped_so_the_origin_header_matches() -> None:
    assert resolve_origin({"FLEXWEEK_ORIGIN": "https://app.example/"}) == "https://app.example"


@pytest.mark.parametrize(
    "bad",
    ["ftp://app.example", "notaurl", "http://127.0.0.1:8000/path", "https://app.example?x=1", "https://"],
)
def test_malformed_origins_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        validate_origin(bad)


def test_remote_http_is_rejected_like_the_server_does() -> None:
    with pytest.raises(ValueError, match="https"):
        validate_origin("http://app.example")


def test_localhost_may_stay_http() -> None:
    assert validate_origin("http://localhost:8000") == "http://localhost:8000"


def test_same_origin_covers_paths_and_default_ports() -> None:
    assert is_same_origin("http://127.0.0.1:8000/api/week", "http://127.0.0.1:8000")
    assert is_same_origin("https://app.example:443/x", "https://app.example")


def test_cross_origin_links_are_external() -> None:
    for url in ("https://github.com/j0nsh1n/FlexWeek", "http://127.0.0.1:9000/", "https://127.0.0.1:8000/"):
        assert not is_same_origin(url, "http://127.0.0.1:8000")


def test_non_web_schemes_are_not_same_origin() -> None:
    assert origin_key("mailto:a@b.example") is None
    assert not is_same_origin("file:///etc/passwd", "http://127.0.0.1:8000")
