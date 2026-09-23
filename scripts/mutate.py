"""Break one rule at a time and check that the test named for it goes red.

    .venv/bin/python scripts/mutate.py                          # every spec in scripts/mutations/
    .venv/bin/python scripts/mutate.py scripts/mutations/zoom.json

A spec is a list of {"name", "file", "old", "new", "test"}: the rule broken, the source file, the
text replaced (found exactly once), what replaces it, and the pytest node that must fail. Each file
is restored after its case, whatever happens. A mutation that leaves its test green means the test
does not guard the rule it claims to; that is a finding, and the script exits 1.

Not part of scripts/verify.py: each case runs pytest on its own, so a full pass takes minutes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "scripts" / "mutations"


def run(case: dict) -> tuple[bool, str]:
    source = ROOT / case["file"]
    original = source.read_text()
    if original.count(case["old"]) != 1:
        return False, f"pattern found {original.count(case['old'])} times in {case['file']}"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "QT_QPA_PLATFORM": "offscreen"}
    try:
        source.write_text(original.replace(case["old"], case["new"]))
        # A same-length edit within a second could reuse a stale .pyc.
        for stale in (source.parent / "__pycache__").glob(source.stem + ".*.pyc"):
            stale.unlink()
        done = subprocess.run(
            [sys.executable, "-m", "pytest", case["test"], "-q", "-x", "-p", "no:cacheprovider"],
            capture_output=True,
            text=True,
            env=env,
            cwd=ROOT,
        )
    finally:
        source.write_text(original)
        for stale in (source.parent / "__pycache__").glob(source.stem + ".*.pyc"):
            stale.unlink()
    why = next((line.strip() for line in done.stdout.splitlines() if line.startswith("E ")), "")
    return done.returncode != 0, why[:110]


def main(paths: list[str]) -> int:
    files = [Path(path) for path in paths] or sorted(SPECS.glob("*.json"))
    survived = 0
    for spec in files:
        for case in json.loads(spec.read_text()):
            red, why = run(case)
            print(f"{'RED  ' if red else 'GREEN'} {spec.stem:10s} {case['name']:56s} {why}")
            survived += not red
    print("every mutation was caught" if not survived else f"{survived} mutation(s) SURVIVED")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
