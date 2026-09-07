from backend.models import ReasonCode

# Partner replaces these with student-facing sentences in Phase 4.
REASON_COPY: dict[ReasonCode, str] = {
    "LOCKED_OVERLAP": "That time is already taken by school, sports, or sleep.",
    "DEADLINE_MISS": "There is no slot left before this deadline.",
    "NO_SLOT_LEFT": "The week is too full to place this task.",
    "PRIORITY_PREEMPT": "A higher-priority task took the last usable slot.",
    "ENERGY_MISMATCH": "Placed, but not in your preferred energy window.",
    "SLEEP_GUARD": "Kept out of the sleep window.",
    "RESHUFFLE_AFTER_MISS": "Moved after a missed block so the rest of the week still fits.",
}


def sentence(code: ReasonCode) -> str:
    return REASON_COPY[code]
