"""Launch FlexWeek as Qt widgets with no browser engine."""

from __future__ import annotations

import sys

from desktop.main import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
