"""The Windows release workflow never waits forever on a process it starts, and still prints the
smoke report when the process fails."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[3] / ".github/workflows/release-windows.yml"


def workflow_step(name: str) -> str:
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    marker = f"      - name: {name}"
    start = lines.index(marker)
    run_line = next(
        i
        for i in range(start + 1, len(lines))
        if lines[i] == "        run: |" or lines[i].startswith("      - name:")
    )
    if lines[run_line] != "        run: |":
        raise AssertionError(f"step {name!r} has no multiline run script")
    script = []
    for line in lines[run_line + 1 :]:
        if line and len(line) - len(line.lstrip()) < 10:
            break
        script.append(line[10:] if line.startswith("          ") else line)
    return "\n".join(script)


def assert_bounded_process(script: str, context: str) -> None:
    assert ".WaitForExit(600000)" in script, context
    assert "Stop-Process -Id $proc.Id -Force" in script, context
    assert not re.search(r"Start-Process[^\n]*\s-Wait(?:\s|$)", script), context


def test_both_release_jobs_have_runner_timeouts() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")
    for job in ("windows", "linux"):
        assert re.search(
            rf"(?m)^  {job}:\n(?:    [^\n]*\n|\n)*?    timeout-minutes: 120$", content
        ), job


def test_package_smoke_wait_is_bounded_and_report_prints_in_finally() -> None:
    script = workflow_step("Smoke-test package layout and the setup Solve")
    assert_bounded_process(script, "package smoke step")
    assert "finally {" in script
    finalizer = script[script.index("finally {") :]
    assert "if (Test-Path $report) { Get-Content $report }" in finalizer
    assert "$proc.ExitCode -ne 0" in script


def test_inno_installer_wait_is_bounded_and_success_code_is_checked() -> None:
    script = workflow_step("Install the installer tools")
    assert_bounded_process(script, "Inno Setup install step")
    assert "if ($proc.ExitCode -ne 0)" in script


def test_install_and_smoke_processes_are_bounded_and_report_prints_in_finally() -> None:
    script = workflow_step("Install, open and uninstall each installer")
    assert script.count(".WaitForExit(600000)") == 2
    assert script.count("Stop-Process -Id $proc.Id -Force") == 2
    assert "Start-Process -Wait" not in script
    assert "$proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010" in script
    assert "finally {" in script
    finalizer = script[script.index("finally {") :]
    assert "if (Test-Path $report) { Get-Content $report }" in finalizer
    assert "$name installed app smoke test timed out after 10 minutes" in script
