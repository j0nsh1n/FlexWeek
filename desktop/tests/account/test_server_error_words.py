"""What the student reads when the server refuses a sign-up or a password: the field that was wrong is
named, and an unrelated 422 gets the general line."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.native.client import PASSWORD_LENGTH_HINT, USERNAME_ERROR, _error


def test_a_bad_username_is_named() -> None:
    err = _error(
        422,
        [
            {
                "type": "string_too_short",
                "loc": ["body", "username"],
                "msg": "String should have at least 3 characters",
                "input": "x",
            }
        ],
    )
    assert err.message == USERNAME_ERROR
    generic = _error(422, [{"type": "value_error", "loc": ["body", "title"], "msg": "title required"}])
    assert "required fields" in generic.message


def test_a_short_password_names_the_field_instead_of_a_generic_check() -> None:
    err = _error(
        422,
        [
            {
                "type": "string_too_short",
                "loc": ["body", "password"],
                "msg": "String should have at least 12 characters",
                "input": "x",
            }
        ],
    )
    assert err.message == PASSWORD_LENGTH_HINT
    generic = _error(422, [{"type": "value_error", "loc": ["body", "title"], "msg": "title required"}])
    assert "required fields" in generic.message
    assert "x" not in err.message
