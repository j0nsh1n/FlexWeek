"""The MCP smoke, against a fake helper that speaks the protocol as scripted.

The real packaged helper is exercised by the release workflow's smoke steps
(desktop/smoke_mcp.py against the extracted tarball and the AppImage). Here a
fake launcher answers the same exchange, so every reason the smoke names is
seen without a Rust build: the passing exchange, and each named failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from desktop import smoke_mcp
from desktop.smoke_mcp import SmokeFailure, client_messages, smoke

FAKE = '''#!{python}
import json
import sys

BEHAVIOR = {behavior!r}
TOOLS = [
    {{"name": name}}
    for name in (
        "get_month", "get_today", "get_week", "list_homework",
        "list_restore_points", "list_routines", "whoami",
    )
]


def reply(identifier, result):
    print(json.dumps({{"jsonrpc": "2.0", "id": identifier, "result": result}}), flush=True)


def sign_in():
    return {{"content": [{{"type": "text", "text": "Please sign in"}}], "isError": True}}


if BEHAVIOR == "stdout-noise":
    print("starting helper", flush=True)
elif BEHAVIOR == "stdout-json-noise":
    print('{{"message": "starting helper"}}', flush=True)

for line in sys.stdin:
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        continue
    identifier = message.get("id")
    method = message.get("method")
    if BEHAVIOR == "silent":
        continue
    elif method == "initialize":
        # Only wrong-protocol fails the handshake; the later stages are tested
        # with a helper that answers it right.
        if BEHAVIOR == "bad-initialize-shape":
            reply(identifier, None)
            continue
        protocol = "2024-11-05" if BEHAVIOR == "wrong-protocol" else "2025-03-26"
        reply(identifier, {{
            "protocolVersion": protocol,
            "capabilities": {{}},
            "serverInfo": {{"name": "fake", "version": "0"}},
        }})
    elif method == "tools/list":
        if BEHAVIOR == "no-list":
            continue
        tools = list(TOOLS)
        if BEHAVIOR == "six-tools":
            tools = [tool for tool in tools if tool["name"] != "list_routines"]
        if BEHAVIOR == "bad-list-shape":
            reply(identifier, None)
        elif BEHAVIOR == "bad-tools-shape":
            reply(identifier, {{"tools": None}})
        else:
            reply(identifier, {{"tools": tools}})
    elif method == "tools/call":
        if BEHAVIOR == "no-today":
            continue
        elif BEHAVIOR == "no-error":
            result = {{"content": [{{"type": "text", "text": "signed in"}}], "isError": False}}
            reply(identifier, result)
        elif BEHAVIOR == "other-text":
            result = {{"content": [{{"type": "text", "text": "Signed in as Bori"}}], "isError": True}}
            reply(identifier, result)
        elif BEHAVIOR == "bad-today-shape":
            reply(identifier, {{"content": None, "isError": True}})
        else:
            reply(identifier, sign_in())
if BEHAVIOR in ("nonzero", "stderr-nonzero"):
    if BEHAVIOR == "stderr-nonzero":
        print("helper exploded", file=sys.stderr, flush=True)
    sys.exit(7)
'''


def fake_helper(tmp_path: Path, behavior: str) -> Path:
    """A launcher that ignores its flags and answers the exchange as behavior says."""
    path = tmp_path / "fake-helper"
    path.write_text(FAKE.format(python=sys.executable, behavior=behavior), encoding="utf-8")
    path.chmod(0o755)
    return path


def test_the_exchange_the_loop_sends_is_not_empty() -> None:
    """replies() loops over this list after asserting it nonempty; a refactor that
    empties it must be seen here before the smoke sends nothing and passes."""
    messages = client_messages()
    assert messages, "the smoke must have an exchange to send"
    assert [message["id"] for message in messages if "id" in message] == [1, 2, 3]


def test_a_helper_that_answers_right_passes(tmp_path: Path) -> None:
    assert smoke(fake_helper(tmp_path, "ok"), timeout=10.0) == {
        1: {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "serverInfo": {"name": "fake", "version": "0"},
            },
        },
        2: {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [{"name": name} for name in smoke_mcp.READ_TOOLS],
            },
        },
        3: {
            "jsonrpc": "2.0",
            "id": 3,
            "result": {"content": [{"type": "text", "text": "Please sign in"}], "isError": True},
        },
    }


def test_failing_helper_stderr_reaches_smoke_stderr(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    helper = fake_helper(tmp_path, "stderr-nonzero")
    with pytest.raises(SmokeFailure):
        smoke(helper, timeout=10.0)
    assert "helper exploded" in capfd.readouterr().err


def test_a_helper_that_echoes_another_protocol_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="echoed protocol '2024-11-05', not '2025-03-26'"):
        smoke(fake_helper(tmp_path, "wrong-protocol"), timeout=10.0)


def test_a_malformed_initialize_result_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="initialize answered None, not a result object"):
        smoke(fake_helper(tmp_path, "bad-initialize-shape"), timeout=10.0)


def test_a_helper_that_lists_the_wrong_tools_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="not exactly the seven read tools"):
        smoke(fake_helper(tmp_path, "six-tools"), timeout=10.0)


def test_a_helper_that_answers_get_today_without_a_refusal_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="not a refusal with isError true"):
        smoke(fake_helper(tmp_path, "no-error"), timeout=10.0)


def test_a_helper_that_says_something_else_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="said 'Signed in as Bori', not 'Please sign in'"):
        smoke(fake_helper(tmp_path, "other-text"), timeout=10.0)


def test_a_helper_that_never_replies_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="no reply to initialize"):
        smoke(fake_helper(tmp_path, "silent"), timeout=2.0)


def test_a_helper_that_skips_tools_list_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="no reply to tools/list"):
        smoke(fake_helper(tmp_path, "no-list"), timeout=10.0)


def test_a_helper_that_skips_get_today_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="no reply to tools/call get_today"):
        smoke(fake_helper(tmp_path, "no-today"), timeout=10.0)


def test_a_malformed_tools_list_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="tools/list answered None, not a result object"):
        smoke(fake_helper(tmp_path, "bad-list-shape"), timeout=10.0)


def test_a_non_list_tools_value_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="tools/list offered None, not a list of tools"):
        smoke(fake_helper(tmp_path, "bad-tools-shape"), timeout=10.0)


def test_a_malformed_get_today_content_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="get_today said None, not 'Please sign in'"):
        smoke(fake_helper(tmp_path, "bad-today-shape"), timeout=10.0)


def test_non_protocol_stdout_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="stdout line was not JSON: b'starting helper'"):
        smoke(fake_helper(tmp_path, "stdout-noise"), timeout=10.0)


def test_non_protocol_json_stdout_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="stdout line was not a JSON-RPC response"):
        smoke(fake_helper(tmp_path, "stdout-json-noise"), timeout=10.0)


def test_a_nonzero_helper_exit_is_named(tmp_path: Path) -> None:
    with pytest.raises(SmokeFailure, match="helper exited with status 7"):
        smoke(fake_helper(tmp_path, "nonzero"), timeout=10.0)
