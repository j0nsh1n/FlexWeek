"""Choices and wording that Settings and the account setup both show."""

from __future__ import annotations

import re
from datetime import datetime

from desktop.native.calendar import DAY_FULL

SPORT_FALLBACK = "Sport or club"
ALARM_TONE_LABELS = {"spotify": "A Spotify song or playlist"}
ALARM_NOTE = "An alarm rings at its time on the days you pick, until you dismiss or snooze it."
# Said above the choice, where it can wrap: as the choice's label it was wider than the page at large text.
DRAG_STEP_QUESTION = "When you drag a block, it moves in steps of this length."
DRAG_STEP_CHOICES = ((5, "5 minutes (more control)"), (15, "15 minutes (quarter hours)"))
PLANNING_STYLES = (
    ("auto", "Plan it for me as I add it", "New homework gets a time straight away."),
    (
        "suggest",
        "Plan when I press Plan my homework",
        "Homework waits in a list until you ask for times.",
    ),
    ("manual", "I'll drag it onto the calendar myself", "The planning button becomes Suggest times."),
)
SPOTIFY_LINK_HINT = (
    "Plays when a block starts if the alarm sound is Spotify, or when focus starts if the focus sound"
    " is Spotify."
)
SPOTIFY_TONE_REST = (
    "It plays in your Spotify app, and stopping the alarm stops it. Reminders before a block and the"
    " end of a focus session play Chime. Without the Spotify app, the link opens and Chime rings too."
)
SPOTIFY_TONE_NOTE = f"{SPOTIFY_LINK_HINT} {SPOTIFY_TONE_REST}"

# Wording the Material Settings pages share with the Widgets pages (copied from settings.py and
# widgets.py; the Widgets originals go with the Widgets styles).
STUDY_HOURS_LINE = "Choose when FlexWeek may plan homework, including hours kept for one class."
SCHOOL_HOURS_NOTE = "The days and times you're at school, so nothing is planned then."
NO_SCHOOL_DAYS = "No school days picked: School won't appear on the calendar."
NO_STUDY_HOURS = "No study hours yet, so homework can go at any time of day."
NO_PROTECTED = "Nothing protected yet. Add practice, family time or a job."
PROTECTED_WORDS = {"downtime": "Downtime", "commute": "Commute", "meal": "Meal"}
DND_NOTE = "Each one stays in the window until you press Got it."
TRAY_NOTE = "FlexWeek waits in the tray, so reminders and alarms still come."
BLOCK_SONG_NOTE = (
    "When a block starts and the alarm sound is Spotify, the Spotify link in Settings plays. Dismiss or"
    " snooze it as you would an alarm."
)
FOCUS_AUDIO_NOTE = (
    "Rain, Lo-Fi and White noise play inside FlexWeek and pause with the timer. Spotify opens the link"
    " from Settings > Alerts when focus starts."
)
NO_SOUND = (
    "No sound played. Check that Volume is above 0 % and that your speakers or headphones are connected"
    " and not muted, then press Play again."
)
SPLIT_ROUNDED = (
    "Focus lengths were rounded to {step} minutes so FlexWeek can split them into sessions and breaks."
)


def ring_days(days: list[int]) -> str:
    """The days an alarm rings, as a student would say them."""
    chosen = sorted(set(days))
    if chosen == list(range(7)):
        return "every day"
    if chosen == [0, 1, 2, 3, 4]:
        return "Monday to Friday"
    if chosen == [5, 6]:
        return "Saturday and Sunday"
    if not chosen:
        return "no days"
    if len(chosen) == 1:
        return DAY_FULL[chosen[0]]
    short = [DAY_FULL[day][:3] for day in chosen]
    return ", ".join(short[:-1]) + " and " + short[-1]


# Help and About: the words and keys both looks show.
ABOUT_LINE = "FlexWeek plans your homework around school, sports and everything else in your week."
ABOUT_HERE = "Your week is saved on this computer, under this account."
HELP_SCREENS = (
    ("Day", "One day hour by hour, with homework that isn't placed yet beside it, ready to drag in."),
    (
        "Week",
        "Your seven-day week. Drag a block to move it, or drag across empty time to add one.",
    ),
    ("Month", "Each date's blocks and the homework due that day; click a date to open it in Day."),
    ("My day", "What is on now and what comes next, to follow once your plan is made."),
)
HELP_PLANNING = (
    "Add homework with its due date and length. Press Plan my homework and FlexWeek finds free time for "
    "it in your study hours, around your fixed times, before it's due. Homework that already has a time "
    "keeps it, unless that time has passed, the work isn't finished and you didn't pin it. Replan all "
    "starts fresh but keeps pinned homework. Anything that doesn't "
    "fit stays under Not placed yet, and Details says why. From the keyboard, press Ctrl+K and type Plan."
)
# Material has no command bar, so its Help ends the planning paragraph before the Ctrl+K sentence.
HELP_PLANNING_MATERIAL = HELP_PLANNING.removesuffix(" From the keyboard, press Ctrl+K and type Plan.")
# Each key in brackets is drawn as a keycap; the words between are drawn plain.
# One group per Settings switch: Number keys, then Letter keys. A group whose switch is off is left out.
HELP_NUMBER_KEYS = (("[1] to [5]", "Day, Week, Month, My day, Settings"),)
HELP_LETTER_KEYS = (
    ("[T]", "Go to today"),
    ("[D] [W] [M]", "Day, Week, Month"),
    ("[J] [K]", "Next and previous week, day or month"),
    ("[C]", "Add homework"),
    ("[P]", "Plan my homework"),
    ("[Z]", "Undo"),
    ("[F]", "Focus screen"),
)
# Keys that answer to neither switch.
HELP_OTHER_KEYS = (
    ("[B] or [Esc]", "Back from My day"),
    ("[Ctrl]+[Shift]+[F]", "Quick focus"),
    ("[F1]", "Help"),
    ("[Ctrl]+[N]", "Add homework"),
    ("[Ctrl]+[K]", "Command bar"),
    ("[Ctrl]+[Shift]+[L]", "Week as a list"),
    ("[Ctrl]+[Z]", "Undo"),
    ("[Ctrl]+[Y] or [Ctrl]+[Shift]+[Z]", "Redo"),
    ("[Ctrl]+[C] then [Ctrl]+[V]", "Copy the selected block, then paste it into the selected day"),
    ("[Ctrl]+[D]", "Duplicate the selected block"),
    ("[Delete]", "Delete the selected block"),
    ("[Ctrl]+[S]", "Save now"),
    ("[Ctrl]+[=] [-] [0]", "Zoom the hours in, out, or back to normal"),
    ("[Ctrl] and the mouse wheel", "Zoom the hours"),
    ("[Esc] while dragging", "Put the block back where it was"),
)
HELP_KEYS = HELP_NUMBER_KEYS + HELP_LETTER_KEYS + HELP_OTHER_KEYS


# The "other" rows that are also true in Material. Its window answers none of the rest: Ctrl+K and B
# do nothing there, and Esc does not put a held card back.
_MATERIAL_OTHER_KEYS = frozenset(
    {
        "[Ctrl]+[Shift]+[F]",
        "[F1]",
        "[Ctrl]+[N]",
        "[Ctrl]+[Shift]+[L]",
        "[Ctrl]+[Z]",
        "[Ctrl]+[Y] or [Ctrl]+[Shift]+[Z]",
        "[Ctrl]+[C] then [Ctrl]+[V]",
        "[Ctrl]+[D]",
        "[Delete]",
        "[Ctrl]+[S]",
        "[Ctrl]+[=] [-] [0]",
        "[Ctrl] and the mouse wheel",
    }
)


def help_keys(numbers: bool, letters: bool, *, material: bool = False) -> tuple[tuple[str, str], ...]:
    """Help's keys as the look answers to them: 1 to 5 only while Number keys is on, the letters only while
    Letter keys is on, and of the rest only the rows that work in that look."""
    rows: list[tuple[str, str]] = []
    if numbers:
        rows += HELP_NUMBER_KEYS
    if letters:
        rows += HELP_LETTER_KEYS
    rows += (row for row in HELP_OTHER_KEYS if not material or row[0] in _MATERIAL_OTHER_KEYS)
    return tuple(rows)


def keys_words(marked: str) -> str:
    """A shortcut as it is said: its keys without their brackets."""
    return marked.replace("[", "").replace("]", "")


def first_lines(notes: str, limit: int = 6) -> str:
    """The top of the release notes, which is where what changed is written.

    GitHub release bodies are Markdown, and a QLabel shows it raw, so the few markers that actually
    appear in these notes are turned into something readable rather than left as "## What changed".
    """
    kept: list[str] = []
    for raw in notes.splitlines():
        line = raw.strip()
        if not line or set(line) <= {"-", "="} and len(line) > 2:
            continue
        line = line.lstrip("#").strip()
        if line.startswith(("- ", "* ")):
            line = "•  " + line[2:]
        kept.append(line.replace("**", ""))
        if len(kept) == limit:
            break
    return "\n".join(kept)


def key_parts(marked: str) -> list[tuple[str, bool]]:
    """A shortcut as (text, is_key) pieces: each key in brackets, then the plain words between them."""
    parts: list[tuple[str, bool]] = []
    for part in re.split(r"(\[[^\]]+\])", marked):
        if not part.strip():
            continue
        cap = part.startswith("[")
        parts.append((part[1:-1] if cap else part.strip(), cap))
    return parts


# Manage account and Copies of this week: the words the Widgets dialogs and the Material sheets share.
ACCOUNT_PASSWORD_NOTE = "Your current password is needed for every change on this page."
ACCOUNT_CODES_NOTE = "Each code signs you in once if you forget your password."
ACCOUNT_DATA_NOTE = "Keep a copy of your account, or of one week or day, in a file."
RESTORE_FIRST = "Choose a saved copy."


def recovery_status(remaining: int | None) -> str:
    """How many recovery codes are left, in the words the account dialog uses."""
    if remaining == 0:
        return "No unused recovery codes remain. Replace them before signing out."
    if remaining == 1:
        return "1 unused recovery code remains."
    if isinstance(remaining, int):
        return f"{remaining} unused recovery codes remain."
    return "Couldn't find out how many recovery codes are left."


def restore_parts(point: dict) -> tuple[str, str]:
    """A restore point as its name and, apart, when it was made and how many weeks it holds."""
    weeks = point.get("weeks_count", point.get("week_count", point.get("weeks", 0)))
    unit = "week" if weeks == 1 else "weeks"
    return str(point.get("label")), f"{point.get('created_at') or ''} · {weeks} {unit}"


def restore_row(point: dict) -> str:
    """One restore point in the list: its name, when it was made and how many weeks it holds."""
    name, detail = restore_parts(point)
    return f"{name} · {detail}"


def restore_summary(preview: dict | None) -> str:
    """What going back to the previewed restore point would change."""
    if not preview:
        return ""
    changes = preview.get("changes") or {}
    weeks = changes.get("weeks") or {}
    homework = changes.get("assignments") or {}
    added = len(weeks.get("added") or []) + len(homework.get("added") or [])
    changed = len(weeks.get("changed") or []) + len(homework.get("changed") or [])
    removed = len(weeks.get("removed") or []) + len(homework.get("removed") or [])
    return f"{added} added, {changed} changed, {removed} removed."


def _joined(parts: list[str]) -> str:
    """"a", "a and b", "a, b, and c"."""
    if len(parts) < 3:
        return " and ".join(parts)
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


def _gone_from_backup(count: int, noun: str) -> str:
    return f"{count} of your {noun} that {'isn' if count == 1 else 'aren'}'t in the backup"


def transfer_summary(preview: dict) -> str:
    """What importing a backup file will do, in sentences: the weeks it adds, replaces and deletes (the
    deleted ones are the account's own, named as such), the homework and routines that change, and
    whether the settings change."""
    changes = preview.get("changes") or {}
    weeks = changes.get("weeks") or {}
    added, replaced, deleted = (len(weeks.get(kind) or []) for kind in ("added", "changed", "removed"))
    parts = []
    if added:
        parts.append(f"adds {added} {'week' if added == 1 else 'weeks'}")
    if replaced:
        parts.append(f"replaces {replaced} of your weeks")
    if deleted:
        parts.append("deletes " + _gone_from_backup(deleted, "weeks"))
    lines = [_joined(parts) + "."] if parts else []
    for key, one, many in (("assignments", "homework", "homework"), ("routines", "routine", "routines")):
        part = changes.get(key) or {}
        differ = len(part.get("added") or []) + len(part.get("changed") or [])
        gone = len(part.get("removed") or [])
        if differ:
            lines.append(f"{differ} {one if differ == 1 else many} {'changes' if differ == 1 else 'change'}.")
        if gone:
            lines.append("It also deletes " + _gone_from_backup(gone, many) + ".")
    if changes.get("preferences_changed"):
        lines.append("Your settings will be replaced.")
    if not lines:
        lines.append("Nothing in it is different from your account.")
    return " ".join(lines)


# Linked phones and syncing: the words and rules the Devices card, the status dot and Material's
# Settings > This computer share.
RELAY_SENTENCE = (
    "When your computer isn't on the same Wi-Fi, FlexWeek uses a public relay run by n0. "
    "It sees that two devices are talking, not what they send."
)
UNREACHABLE_WORDS = "Couldn't reach your phone. Open FlexWeek on it, then try again."
DOT_WORDS = {
    "off": "",
    "idle": "Waiting for a linked phone to sync",
    "syncing": "Syncing with your phone",
    "synced": "Synced with your phone",
    "problem": "Couldn't reach your phone",
}


def seen_words(last_seen_ms: str | None, now_ms: int) -> str:
    """When a phone was last seen, in the card's words. last_seen is Unix milliseconds as text."""
    if not last_seen_ms:
        return "Not synced yet"
    seen = int(last_seen_ms)
    minutes = max(0, now_ms - seen) // 60_000
    if minutes < 1:
        return "Synced just now"
    if minutes < 60:
        return f"Synced {minutes} min ago"
    if minutes < 24 * 60:
        return f"Synced {minutes // 60} h ago"
    return f"Last seen on {datetime.fromtimestamp(seen / 1000):%A}"


def clock_warning_words(count: int) -> str:
    if count <= 0:
        return ""
    noun, verb = ("change", "was") if count == 1 else ("changes", "were")
    return f"Your phone's clock looks wrong. {count} {noun} {verb} held back."


def sync_state(status: dict, linked: bool) -> str:
    """Which picture the status dot shows. A failed call stays a problem until one call works."""
    if not linked:
        return "off"
    if status["syncing"]:
        return "syncing"
    if status["last_error"]:
        return "problem"
    if status["last_sync_ms"] is None:
        return "idle"
    return "synced"


# The pairing code's own words while it is open, and why it closed. The engine allows one phone per code.
PAIR_ONCE = "It works once."
PAIR_CLOSED = "That code isn't active anymore. Start a new one."


def countdown_words(seconds: int) -> str:
    minutes, rest = divmod(max(0, seconds), 60)
    return f"Code works for {minutes}:{rest:02d}"


def tries_words(tries: int) -> str:
    return "1 try left" if tries == 1 else f"{tries} tries left"


def pair_problem(state: str) -> str:
    if state == "expired":
        return "That code has expired. Start a new one."
    if state == "too_many_tries":
        return "Too many wrong tries. Start a new code."
    return ""
