"""Fail a release build whose tag, VERSION or CHANNEL disagree.

    python scripts/check_release_tag.py --tag "$TAG"

Reads desktop/native/version.py as text (the engine module is not built yet when the release
workflow runs this). An empty tag is a build that uploads nothing, so only the channel is checked.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_VERSION_FILE = Path(__file__).resolve().parents[1] / "desktop/native/version.py"


def constant(text: str, name: str) -> str | None:
    found = re.search(rf'^{name} = "([^"]*)"', text, flags=re.M)
    return found.group(1) if found else None


def problems(tag: str, text: str) -> list[str]:
    version = constant(text, "VERSION")
    channel = constant(text, "CHANNEL")
    found = []
    if version is None:
        found.append("desktop/native/version.py has no VERSION")
    if channel != "release":
        found.append(f'CHANNEL is {channel!r} in desktop/native/version.py, not "release"')
    if tag:
        match = re.fullmatch(r"v(\d+\.\d+\.\d+)", tag)
        if match is None:
            found.append(f"tag {tag!r} is not a release tag like v1.3.0")
        elif version is not None and match.group(1) != version:
            found.append(f"tag {tag} does not match VERSION {version} in desktop/native/version.py")
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="")
    parser.add_argument("--version-file", type=Path, default=DEFAULT_VERSION_FILE)
    args = parser.parse_args()
    found = problems(args.tag, args.version_file.read_text(encoding="utf-8"))
    for line in found:
        print(f"error: {line}", file=sys.stderr)
    if not found:
        print(f"release check ok: tag {args.tag or '(none)'}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
