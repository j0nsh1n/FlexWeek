"""The copy started after a graphics failure is started the way FlexWeek itself was started."""

from desktop.native.cpu_drawing import new_copy_command


def test_an_appimage_starts_again_from_the_appimage_file_not_its_mount() -> None:
    command = new_copy_command(
        frozen=True,
        appimage="/home/student/Apps/FlexWeek-x86_64.AppImage",
        executable="/tmp/.mount_FlexWeAbc/FlexWeek",
        argv=["/tmp/.mount_FlexWeAbc/FlexWeek", "--database", "/home/student/plan.db"],
        orig_argv=["/tmp/.mount_FlexWeAbc/FlexWeek", "--database", "/home/student/plan.db"],
    )
    assert command == ["/home/student/Apps/FlexWeek-x86_64.AppImage", "--database", "/home/student/plan.db"]


def test_a_packaged_build_starts_its_own_executable_with_its_arguments() -> None:
    command = new_copy_command(
        frozen=True,
        appimage=None,
        executable=r"C:\Users\student\AppData\Local\Programs\FlexWeek\FlexWeek.exe",
        argv=[r"C:\Users\student\AppData\Local\Programs\FlexWeek\FlexWeek.exe"],
        orig_argv=[r"C:\Users\student\AppData\Local\Programs\FlexWeek\FlexWeek.exe"],
    )
    assert command == [r"C:\Users\student\AppData\Local\Programs\FlexWeek\FlexWeek.exe"]


def test_a_source_run_repeats_the_interpreter_and_its_arguments() -> None:
    command = new_copy_command(
        frozen=False,
        appimage=None,
        executable="/repo/.venv/bin/python",
        argv=["/repo/desktop/main.py"],
        orig_argv=["/repo/.venv/bin/python", "-m", "desktop.main"],
    )
    assert command == ["/repo/.venv/bin/python", "-m", "desktop.main"]
