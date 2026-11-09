"""The fixed block the fixed-time editor's tests open: Soccer practice on Tuesday and Thursday."""

from __future__ import annotations


def soccer(**fields: object) -> dict:
    return {
        "id": "soccer",
        "title": "Soccer practice",
        "kind": "locked",
        "category": "sport",
        "start": "16:00",
        "duration_min": 90,
        "days": [1, 3],
        **fields,
    }
