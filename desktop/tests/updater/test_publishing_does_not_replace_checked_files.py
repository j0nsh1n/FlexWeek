"""Publishing a release starts the packaging workflow again. It must never replace a file that is
already on the release: those were checked, and the updater is already offering them."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = (ROOT / ".github/workflows/release-windows.yml").read_text(encoding="utf-8")
CHECKLIST = (ROOT / "docs/github-release.md").read_text(encoding="utf-8")


def upload_step(job: str) -> str:
    start = WORKFLOW.index(f"\n  {job}:\n")
    step = WORKFLOW.index("      - name: Attach to the release", start)
    following = re.search(r"\n  \S|\n      - name:", WORKFLOW[step + 10 :])
    end = step + 10 + following.start() if following else len(WORKFLOW)
    return WORKFLOW[step:end]


def test_no_upload_replaces_an_existing_file() -> None:
    assert "--clobber" not in WORKFLOW


def test_each_upload_asks_the_release_which_files_it_already_has() -> None:
    for job in ("windows", "linux"):
        step = upload_step(job)
        assert "gh release view" in step, job
        assert "gh release upload" in step, job
        assert "is already on the release; leaving it as it is" in step, job


def test_the_windows_upload_goes_file_by_file() -> None:
    step = upload_step("windows")
    for name in (
        "FlexWeek-Windows-x64-Setup.exe",
        "FlexWeek-Windows-x64-Setup.exe.sha256",
        "FlexWeek-Windows-x64.msi",
        "FlexWeek-Windows-x64.msi.sha256",
    ):
        assert name in step


def test_the_linux_upload_goes_file_by_file() -> None:
    step = upload_step("linux")
    for name in (
        "FlexWeek-Linux-x86_64.tar.gz",
        "FlexWeek-Linux-x86_64.tar.gz.sha256",
        "FlexWeek-x86_64.AppImage",
        "FlexWeek-x86_64.AppImage.sha256",
    ):
        assert name in step


def test_the_release_checklist_covers_every_file_and_the_order() -> None:
    assert "## Release checklist" in CHECKLIST
    for needle in (
        "FlexWeek-Android-",
        ".apk.sha256",
        "apksigner verify --print-certs",
        "sha256sum -c",
        "scripts/check_release_tag.py",
        "scripts/dev-release.sh",
        "@coderabbitai review",
        "Release packages",
        "/releases/latest",
        "draft",
    ):
        assert needle in CHECKLIST, needle
