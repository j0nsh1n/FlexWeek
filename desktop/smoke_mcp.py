"""Smoke the packaged assistant helper: the package launcher starts it with --mcp.

    python3 desktop/smoke_mcp.py <package launcher> [--timeout seconds]

The launcher is the tarball's FlexWeek script or the AppImage, both of which
dispatch --mcp to the helper inside the package. The helper is started read
only over a fresh empty data folder, with HOME pointed at a fresh empty
directory so no kept session can exist, and speaks newline-delimited JSON-RPC
on stdin and stdout. PASS needs the echoed protocol version, exactly the seven
read tools, and get_today answering "Please sign in". Anything else names the
reason and fails.
"""

from __future__ import annotations

import argparse
import json
import os
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROTOCOL_VERSION = "2025-03-26"
READ_TOOLS = (
    "get_month",
    "get_today",
    "get_week",
    "list_homework",
    "list_restore_points",
    "list_routines",
    "whoami",
)
SIGN_IN = "Please sign in"
# A reply to every request with an id; notifications/initialized draws none.
REPLY_IDS = (1, 2, 3)


class SmokeFailure(Exception):
    """One named reason the packaged helper is not good to ship."""


def client_messages() -> list[dict]:
    """The exchange a passing helper must answer, in order."""
    return [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "flexweek-smoke", "version": "0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "get_today", "arguments": {}},
        },
    ]


def replies(launcher: Path, home: Path, data_dir: Path, timeout: float) -> dict[int, dict]:
    """Start the launcher, send the exchange, return the replies by their id."""
    messages = client_messages()
    if not messages:
        raise SmokeFailure("no request messages to send")
    env = dict(os.environ)
    # A fresh empty home holds no kept session, so the read tools must refuse.
    # It has to exist before the launch: a helper that cannot find its home
    # folder fails in its own way instead of answering.
    home.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(home)
    # The AppImage runtime extracts instead of mounting, which a machine
    # without FUSE needs; the shell launcher ignores it.
    env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    child = subprocess.Popen(
        [str(launcher), "--mcp", "--read-only", "--data-dir", str(data_dir)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if child.stdin is None or child.stdout is None:
        child.kill()
        raise SmokeFailure("could not open helper stdin and stdout")
    reader = selectors.DefaultSelector()
    reader.register(child.stdout, selectors.EVENT_READ)
    try:
        for message in messages:
            child.stdin.write((json.dumps(message) + "\n").encode())
        child.stdin.flush()
        found: dict[int, dict] = {}
        buffer = b""
        deadline = time.monotonic() + timeout
        while len(found) < len(REPLY_IDS) and time.monotonic() < deadline:
            events = reader.select(timeout=max(0.0, deadline - time.monotonic()))
            if not events:
                break
            chunk = os.read(child.stdout.fileno(), 65536)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                try:
                    reply = json.loads(line)
                except json.JSONDecodeError:
                    raise SmokeFailure(f"stdout line was not JSON: {line!r}") from None
                if (
                    not isinstance(reply, dict)
                    or reply.get("jsonrpc") != "2.0"
                    or reply.get("id") not in REPLY_IDS
                ):
                    raise SmokeFailure(f"stdout line was not a JSON-RPC response: {reply!r}")
                if reply["id"] in found:
                    raise SmokeFailure(f"stdout repeated response id {reply['id']}")
                found[reply["id"]] = reply
        return found
    finally:
        # The helper serves until stdin ends; closing it is how the smoke walk
        # ends. A helper that will not leave is killed, not waited on for ever.
        child.stdin.close()
        try:
            return_code = child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            return_code = child.wait(timeout=5)
        reader.close()
        if return_code != 0:
            raise SmokeFailure(f"helper exited with status {return_code}")


def check(found: dict[int, dict]) -> None:
    """PASS needs the echoed protocol, exactly the seven read tools and a
    sign-in refusal from get_today. Every shape the helper could send is
    answered with a named reason, never a crash of the smoke itself."""
    handshake = found.get(1)
    if handshake is None:
        raise SmokeFailure("no reply to initialize")
    result = handshake.get("result")
    if not isinstance(result, dict):
        raise SmokeFailure(f"initialize answered {result!r}, not a result object")
    echoed = result.get("protocolVersion")
    if echoed != PROTOCOL_VERSION:
        raise SmokeFailure(f"initialize echoed protocol {echoed!r}, not {PROTOCOL_VERSION!r}")

    listing = found.get(2)
    if listing is None:
        raise SmokeFailure("no reply to tools/list")
    listing_result = listing.get("result")
    if not isinstance(listing_result, dict):
        raise SmokeFailure(f"tools/list answered {listing_result!r}, not a result object")
    tools = listing_result.get("tools")
    if not isinstance(tools, list):
        raise SmokeFailure(f"tools/list offered {tools!r}, not a list of tools")
    names = sorted(str(tool.get("name")) for tool in tools if isinstance(tool, dict))
    if names != sorted(READ_TOOLS):
        raise SmokeFailure(
            f"tools/list offered {names}, not exactly the seven read tools {sorted(READ_TOOLS)}"
        )

    today = found.get(3)
    if today is None:
        raise SmokeFailure("no reply to tools/call get_today")
    result = today.get("result")
    if not isinstance(result, dict) or result.get("isError") is not True:
        raise SmokeFailure(f"get_today answered {result!r}, not a refusal with isError true")
    content = result.get("content")
    if isinstance(content, list) and content and isinstance(content[0], dict):
        text = content[0].get("text")
    else:
        text = None
    if text != SIGN_IN:
        raise SmokeFailure(f"get_today said {text!r}, not {SIGN_IN!r}")


def smoke(launcher: Path, timeout: float = 60.0) -> dict[int, dict]:
    """Run the packaged helper through the exchange and check what it answered."""
    scratch = Path(tempfile.mkdtemp(prefix="flexweek-mcp-smoke-"))
    try:
        found = replies(
            launcher, home=scratch / "home", data_dir=scratch / "data", timeout=timeout
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    check(found)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("launcher", type=Path, help="the tarball's FlexWeek script or the AppImage")
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds to wait for a reply")
    args = parser.parse_args(argv)
    if not args.launcher.is_file():
        print(f"No package launcher at {args.launcher}", file=sys.stderr)
        return 2
    try:
        smoke(args.launcher, timeout=args.timeout)
    except SmokeFailure as failure:
        print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"PASS: the packaged helper answered the protocol, the seven read tools and {SIGN_IN!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
