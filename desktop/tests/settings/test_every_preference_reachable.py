"""Every account preference has to be reachable from the desktop app, or be named as web-only.

The browser shell was retired, so the native client is how most students meet FlexWeek. Ten of the
twenty-six preferences could only be set from the web app, including `start_at_login`, a desktop
feature the desktop app could not turn on.
"""

from __future__ import annotations

import json
import pathlib

import flexweek_engine  # type: ignore[import-untyped]

ROOT = pathlib.Path(__file__).parents[3]

# Settings the desktop app has nothing to do with. Each needs a reason, not just an entry.
WEB_ONLY = {
    "sidebar_collapsed": "the sidebar is a web layout; the desktop app has no sidebar",
    "sidebar_width_px": "as above",
}
# Written for you, not chosen. save_preferences derives the light or dark axis from the pack.
DERIVED = {
    "theme": "follows theme_pack, set by the engine's preferences_body for NativeSession.save_preferences"
}


def native_source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "desktop" / "native").rglob("*.py"))


def test_every_preference_is_reachable_from_the_desktop_app() -> None:
    source = native_source()
    unreachable = [
        field
        for field in flexweek_engine.preference_fields()
        if field not in source and field not in WEB_ONLY
    ]
    assert unreachable == [], f"the desktop app cannot set: {unreachable}"


def test_a_derived_preference_really_is_derived() -> None:
    # The save's body comes from the engine since 2.0.0's P4 (session/preferences.rs): whatever theme the
    # caller holds, the pack decides it.
    current = {"theme": "nocturne", "theme_pack": "dark-frost"}
    body = json.loads(
        flexweek_engine.session_preferences_body(json.dumps(current), json.dumps({"theme_pack": "slate"}))
    )
    assert set(DERIVED) == {"theme"}
    assert body["theme"] == "slate"


def test_every_web_only_preference_says_why() -> None:
    for field, reason in WEB_ONLY.items():
        assert field in flexweek_engine.preference_fields(), f"{field} is no longer a preference"
        assert reason, field
