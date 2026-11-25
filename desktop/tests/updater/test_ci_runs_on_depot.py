"""Jonathan, 2026-11-24: CI runs on Depot for its parallel runners. GitHub Actions keeps only what
Depot cannot run: CodeQL (its action looks up its own GitHub run) and the Windows installers (Depot
has no Windows runners). Nothing runs on both, so a check is never paid for twice."""

from __future__ import annotations

import re

from desktop.tests.updater.release_workflows import LINUX, ROOT, WINDOWS


def _jobs(text: str) -> list[str]:
    return re.findall(r"(?m)^  ([a-z][a-z0-9_-]*):\n", text.split("\njobs:\n", 1)[1])


def test_github_actions_keeps_only_codeql_and_the_windows_release() -> None:
    names = sorted(path.name for path in (ROOT / ".github/workflows").glob("*.y*ml"))
    assert names == ["codeql.yml", "release-windows.yml"]
    assert _jobs(WINDOWS.read_text(encoding="utf-8")) == ["windows"]


def test_depot_runs_the_checks_the_developer_build_and_the_linux_release() -> None:
    names = sorted(path.name for path in (ROOT / ".depot/workflows").glob("*.y*ml"))
    assert names == ["dev-build.yml", "release-linux.yml", "verify.yml"]
    assert _jobs(LINUX.read_text(encoding="utf-8")) == ["linux"]
    for path in (ROOT / ".depot/workflows").glob("*.y*ml"):
        runners = re.findall(r"(?m)^\s*runs-on: (\S+)", path.read_text(encoding="utf-8"))
        assert runners and all(runner.startswith("depot-") for runner in runners), (path.name, runners)


def test_a_developer_build_release_skips_the_windows_installers() -> None:
    """Each developer build is published as a release (tag dev, and dev-<sha> for the ones kept), which
    used to start the Windows job only for its tag check to fail and leave a red mark on main. Version
    tags (v1.5.1), hand runs and pull requests still build."""
    job = WINDOWS.read_text(encoding="utf-8").split("\n  windows:\n", 1)[1].split("\n    steps:\n", 1)[0]
    conditions = re.findall(r"(?m)^    if: (.+)$", job)
    assert conditions == ["github.event_name != 'release' || startsWith(github.event.release.tag_name, 'v')"]
