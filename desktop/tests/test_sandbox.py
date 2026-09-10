from __future__ import annotations

from pathlib import Path

from desktop.sandbox import DISABLE_VARIABLE, disable_sandbox_if_blocked


def fake_proc(root: Path, **values: str) -> Path:
    for name, value in values.items():
        path = root / name.replace("__", "/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value + "\n")
    return root


def test_stock_ubuntu_apparmor_restriction_turns_the_sandbox_off(tmp_path: Path) -> None:
    proc = fake_proc(tmp_path, sys__kernel__apparmor_restrict_unprivileged_userns="1")
    env: dict[str, str] = {}
    reason = disable_sandbox_if_blocked(env, proc, "linux")
    assert reason == "sys/kernel/apparmor_restrict_unprivileged_userns"
    assert env == {DISABLE_VARIABLE: "1"}


def test_namespaces_allowed_keeps_the_sandbox_on(tmp_path: Path) -> None:
    proc = fake_proc(
        tmp_path,
        sys__kernel__apparmor_restrict_unprivileged_userns="0",
        sys__user__max_user_namespaces="63328",
    )
    env: dict[str, str] = {}
    assert disable_sandbox_if_blocked(env, proc, "linux") is None
    assert env == {}


def test_missing_sysctls_keep_the_sandbox_on(tmp_path: Path) -> None:
    env: dict[str, str] = {}
    assert disable_sandbox_if_blocked(env, tmp_path, "linux") is None
    assert env == {}


def test_zero_user_namespaces_turns_the_sandbox_off(tmp_path: Path) -> None:
    proc = fake_proc(tmp_path, sys__user__max_user_namespaces="0")
    env: dict[str, str] = {}
    assert disable_sandbox_if_blocked(env, proc, "linux") == "sys/user/max_user_namespaces"
    assert env[DISABLE_VARIABLE] == "1"


def test_a_value_the_user_set_and_other_platforms_are_left_alone(tmp_path: Path) -> None:
    proc = fake_proc(tmp_path, sys__kernel__apparmor_restrict_unprivileged_userns="1")
    chosen = {DISABLE_VARIABLE: "0"}
    assert disable_sandbox_if_blocked(chosen, proc, "linux") is None
    assert chosen == {DISABLE_VARIABLE: "0"}
    windows: dict[str, str] = {}
    assert disable_sandbox_if_blocked(windows, proc, "win32") is None
    assert windows == {}
