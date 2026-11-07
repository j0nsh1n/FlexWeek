"""The desktop app draws with Qt widgets, never a web engine, and its client only talks to this computer."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import sys

import pytest
from PySide6.QtWidgets import QApplication

from desktop.native.client import NativeClient
from desktop.tests.window_support import qapp  # noqa: F401


def web_engine_modules() -> list[str]:
    return [name for name in sys.modules if "WebEngine" in name or "QtWebEngine" in name]


def test_the_app_does_not_load_a_web_engine(qapp: QApplication) -> None:
    assert web_engine_modules() == []
    import desktop.main as desktop_main

    assert "WebEngine" not in desktop_main.__doc__
    assert web_engine_modules() == []


def test_the_client_only_accepts_a_loopback_origin(qapp: QApplication) -> None:
    NativeClient("http://127.0.0.1:8765", qapp)
    with pytest.raises(ValueError, match="canonical HTTP loopback origin"):
        NativeClient("https://example.com")
    with pytest.raises(ValueError, match="canonical HTTP loopback origin"):
        NativeClient("http://127.0.0.1")
