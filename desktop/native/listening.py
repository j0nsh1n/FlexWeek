"""The network sockets this process listens on, for the smoke run's report and the tests: FlexWeek
answers its own requests and should listen on nothing unless a phone is paired. No Qt imports."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

# A TCP socket's state in /proc/net/tcp when it listens.
LISTEN = "0A"


def listening_sockets() -> list[str] | None:
    """Each TCP socket in the listening state and each bound UDP socket this process holds, IPv4 and
    IPv6, as "table address"; None where Linux's socket tables cannot be read (other systems)."""
    if not Path("/proc/self/net/tcp").exists():
        return None
    mine = set()
    for fd in Path("/proc/self/fd").iterdir():
        with contextlib.suppress(OSError):
            target = os.readlink(fd)
            if target.startswith("socket:["):
                mine.add(target[len("socket:[") : -1])
    found = []
    for table in ("tcp", "tcp6", "udp", "udp6"):
        path = Path(f"/proc/self/net/{table}")
        # A kernel without IPv6 has no tcp6 or udp6 table.
        if not path.exists():
            continue
        for line in path.read_text().splitlines()[1:]:
            fields = line.split()
            local, state, inode = fields[1], fields[3], fields[9]
            if inode in mine and (table.startswith("udp") or state == LISTEN):
                found.append(f"{table} {local}")
    return found
