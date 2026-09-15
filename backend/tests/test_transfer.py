"""Transfer size helper. Expected values are from docs/stage6-contract.md."""

from __future__ import annotations

import json

from backend.limits import MAX_BODY
from backend.transfer import transfer_apply_bytes, transfer_apply_envelope, transfer_fits


def test_apply_envelope_is_larger_than_the_snapshot_alone() -> None:
    snapshot = {"format": 3, "weeks": []}
    wrapped = json.dumps(transfer_apply_envelope(snapshot), separators=(",", ":")).encode()
    bare = json.dumps(snapshot, separators=(",", ":")).encode()
    assert transfer_apply_bytes(snapshot) == len(wrapped)
    assert len(wrapped) > len(bare)
    assert transfer_fits(snapshot) is True


def test_a_snapshot_past_the_write_cap_does_not_fit() -> None:
    snapshot = {"blob": "x" * MAX_BODY}
    assert transfer_apply_bytes(snapshot) > MAX_BODY
    assert transfer_fits(snapshot) is False
