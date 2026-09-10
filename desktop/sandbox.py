"""Chromium sandbox availability on Linux. No Qt imports.

Qt WebEngine is Chromium, and Chromium's renderer sandbox needs unprivileged
user namespaces. Ubuntu 23.10 and later restrict those through AppArmor unless
an app has its own AppArmor profile, which needs root to install. Without the
sandbox Chromium aborts with "No usable sandbox", so a student on a stock
Ubuntu would see FlexWeek start and then show nothing.
"""

from __future__ import annotations

import sys
from collections.abc import MutableMapping
from pathlib import Path

DISABLE_VARIABLE = "QTWEBENGINE_DISABLE_SANDBOX"

# Each sysctl, and the value that means unprivileged user namespaces are off.
BLOCKING_SYSCTLS = {
    "sys/kernel/apparmor_restrict_unprivileged_userns": "1",
    "sys/kernel/unprivileged_userns_clone": "0",
    "sys/user/max_user_namespaces": "0",
}


def blocking_sysctl(proc: Path = Path("/proc")) -> str | None:
    """The first sysctl that stops Chromium's namespace sandbox, or None."""
    for name, blocked in BLOCKING_SYSCTLS.items():
        try:
            if (proc / name).read_text().strip() == blocked:
                return name
        except OSError:
            continue
    return None


def disable_sandbox_if_blocked(
    env: MutableMapping[str, str], proc: Path = Path("/proc"), platform: str = sys.platform
) -> str | None:
    """Turn the renderer sandbox off only when the kernel would refuse it.

    Returns the sysctl that caused it, or None when nothing changed. A value the
    user already set is left alone. The window only ever renders FlexWeek's own
    origin; every other link is handed to the system browser.
    """
    if not platform.startswith("linux") or DISABLE_VARIABLE in env:
        return None
    reason = blocking_sysctl(proc)
    if reason is not None:
        env[DISABLE_VARIABLE] = "1"
    return reason
