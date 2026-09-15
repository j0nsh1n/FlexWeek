"""Recovery-code formatting and hashing. Expected values are from docs/stage6-contract.md."""

from __future__ import annotations

import re

from backend.recovery import (
    generate_recovery_codes,
    hash_recovery_code,
    normalize_recovery_code,
    recovery_code_matches,
)

CODE = "a1b2-c3d4-e5f6-7890"
DISPLAY = re.compile(r"[0-9a-f]{4}(?:-[0-9a-f]{4}){3}\Z")


def test_normalize_strips_hyphens_and_case() -> None:
    assert normalize_recovery_code("A1B2-C3D4-E5F6-7890") == "a1b2c3d4e5f67890"
    assert normalize_recovery_code("a1b2c3d4e5f67890") == "a1b2c3d4e5f67890"


def test_same_code_hashes_equal_with_or_without_hyphens() -> None:
    assert hash_recovery_code(CODE) == hash_recovery_code("A1B2C3D4E5F67890")
    assert hash_recovery_code(CODE) != hash_recovery_code("a1b2-c3d4-e5f6-7891")
    assert recovery_code_matches("A1B2-C3D4-E5F6-7890", hash_recovery_code(CODE))
    assert not recovery_code_matches("a1b2-c3d4-e5f6-7891", hash_recovery_code(CODE))


def test_generated_codes_are_eight_unique_hyphenated_hex_strings() -> None:
    codes = generate_recovery_codes()
    assert len(codes) == 8
    assert len(set(codes)) == 8
    assert all(DISPLAY.fullmatch(code) for code in codes)
    assert all(hash_recovery_code(code) != code for code in codes)
