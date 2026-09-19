"""Open the look-concepts mock-up in the system browser.

Run from the repo root:

    python docs/mockups/look-concepts/demo.py

This is a mock-up, not FlexWeek. It opens index.html. It reads and writes no
FlexWeek data.
"""

from __future__ import annotations

import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    webbrowser.open(HERE.joinpath("index.html").as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
