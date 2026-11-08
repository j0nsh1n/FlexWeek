"""The AppImage: its checksum names only the file, and its AppRun stops with one plain message when
libEGL is missing."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_appimage_checksum_names_only_the_file(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "FlexWeek").write_text("#!/bin/sh\n", encoding="utf-8")
    (bundle / "FlexWeek").chmod(0o755)
    # Stands in for appimagetool, which make-appimage.sh uses from PATH before downloading it.
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "appimagetool").write_text('#!/bin/sh\nprintf "appimage" > "$2"\n', encoding="utf-8")
    (tools / "appimagetool").chmod(0o755)
    output = tmp_path / "deep" / "release" / "FlexWeek-x86_64.AppImage"
    env = {**os.environ, "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}"}
    subprocess.run(
        ["bash", str(ROOT / "packaging/make-appimage.sh"), str(bundle), str(output)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    checksum = output.with_name("FlexWeek-x86_64.AppImage.sha256")
    assert checksum.read_text(encoding="utf-8").split()[1] == "FlexWeek-x86_64.AppImage"
    assert "/" not in checksum.read_text(encoding="utf-8")
    subprocess.run(
        ["sha256sum", "-c", checksum.name], cwd=output.parent, check=True, capture_output=True, timeout=60
    )


def _build_appdir(tmp_path: Path) -> Path:
    # A fake appimagetool that keeps the AppDir beside the output, so the test can run its AppRun.
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "FlexWeek").write_text('#!/bin/sh\ntouch "$(dirname "$0")/ran"\n', encoding="utf-8")
    (bundle / "FlexWeek").chmod(0o755)
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "appimagetool").write_text(
        '#!/bin/sh\ncp -a "$1" "$2.appdir" && printf "appimage" > "$2"\n', encoding="utf-8"
    )
    (tools / "appimagetool").chmod(0o755)
    output = tmp_path / "release" / "FlexWeek-x86_64.AppImage"
    env = {**os.environ, "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}"}
    subprocess.run(
        ["bash", str(ROOT / "packaging/make-appimage.sh"), str(bundle), str(output)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return output.with_name("FlexWeek-x86_64.AppImage.appdir")


def _run_apprun(appdir: Path, ldconfig_output: str, library_path: str) -> subprocess.CompletedProcess[str]:
    # A fake ldconfig stands in for the system library cache, so a test can say libEGL is absent.
    fakes = appdir.parent / "fake-bin"
    fakes.mkdir(exist_ok=True)
    (fakes / "ldconfig").write_text(f"#!/bin/sh\nprintf '%s' '{ldconfig_output}'\n", encoding="utf-8")
    (fakes / "ldconfig").chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fakes}{os.pathsep}{os.environ['PATH']}",
        "LD_LIBRARY_PATH": library_path,
    }
    return subprocess.run([str(appdir / "AppRun")], env=env, capture_output=True, text=True, timeout=60)


# A system cache that lists libraries, but not libEGL.
WITHOUT_EGL = "\tlibc.so.6 (libc6,x86-64) => /lib64/libc.so.6\n"


def test_apprun_stops_with_one_message_when_libegl_is_missing(tmp_path: Path) -> None:
    appdir = _build_appdir(tmp_path)
    result = _run_apprun(appdir, ldconfig_output=WITHOUT_EGL, library_path="")
    assert result.returncode != 0
    assert "libEGL.so.1" in result.stderr
    assert "sudo apt install libegl1" in result.stderr
    assert "sudo dnf install libglvnd-egl" in result.stderr
    assert "Traceback" not in result.stderr
    assert not (appdir / "usr/lib/FlexWeek/ran").exists()


def test_apprun_starts_the_app_when_the_system_cache_has_libegl(tmp_path: Path) -> None:
    appdir = _build_appdir(tmp_path)
    result = _run_apprun(appdir, "\tlibEGL.so.1 (libc6,x86-64) => /lib64/libEGL.so.1\n", "")
    assert result.returncode == 0, result.stderr
    assert (appdir / "usr/lib/FlexWeek/ran").exists()


def test_apprun_accepts_libegl_found_on_library_path(tmp_path: Path) -> None:
    appdir = _build_appdir(tmp_path)
    libs = tmp_path / "libs"
    libs.mkdir()
    (libs / "libEGL.so.1").write_text("", encoding="utf-8")
    result = _run_apprun(appdir, ldconfig_output=WITHOUT_EGL, library_path=str(libs))
    assert result.returncode == 0, result.stderr
    assert (appdir / "usr/lib/FlexWeek/ran").exists()


def test_apprun_starts_when_there_is_no_library_cache_to_read(tmp_path: Path) -> None:
    # Some systems have no ldconfig cache; the check cannot tell there, so it must not refuse.
    appdir = _build_appdir(tmp_path)
    result = _run_apprun(appdir, ldconfig_output="", library_path="")
    assert result.returncode == 0, result.stderr
    assert (appdir / "usr/lib/FlexWeek/ran").exists()
