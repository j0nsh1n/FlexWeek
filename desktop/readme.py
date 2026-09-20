"""Fill the placeholder lines in a packaged README. No Qt imports.

FLEXWEEK_WEB_URL used to point at a hosted browser version. That version was
retired on 2026-09-19, so the variable is honoured only if someone sets it; with
it unset, which is the normal case, the README says there is no web version.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

ONLINE = "On a Chromebook or a computer that cannot run this app, use the web version: {url}"
OFFLINE = "FlexWeek is a Windows and Linux desktop app. There is no web version."
ONLINE_FALLBACK = "Use the web version instead: {url}"
OFFLINE_FALLBACK = "Upgrade to one of the versions listed above."


def render(template: str, web_url: str = "") -> str:
    url = web_url.strip()
    if url:
        return template.replace("@WEB_VERSION@", ONLINE.format(url=url)).replace(
            "@WEB_FALLBACK@", ONLINE_FALLBACK.format(url=url)
        )
    return template.replace("@WEB_VERSION@", OFFLINE).replace("@WEB_FALLBACK@", OFFLINE_FALLBACK)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    args.destination.write_text(
        render(args.source.read_text(encoding="utf-8"), os.environ.get("FLEXWEEK_WEB_URL", "")),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
