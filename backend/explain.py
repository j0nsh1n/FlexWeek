from backend.models import ReasonCode, SlackStatus

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


def slack_sentence(slack_min: int, status: SlackStatus) -> str:
    if slack_min == 0:
        return "Scheduled to finish exactly at the deadline."
    hours, minutes = divmod(slack_min, 60)
    amount = f"{hours}h" if minutes == 0 else f"{hours}h {minutes}m" if hours else f"{minutes}m"
    lead = {"danger": "Very little room", "tight": "Limited room", "ok": "Room"}[status]
    return f"{lead}: scheduled to finish {amount} before the deadline."
