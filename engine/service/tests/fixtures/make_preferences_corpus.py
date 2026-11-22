"""The preferences parity corpus: generated preferences and what pydantic's Preferences makes of each
(the written preferences, or a refusal). Fixed seed, so the corpus is the same on every run. Run from the
repository root: PYTHONPATH=. .venv/bin/python <this file> <out.json> 2000."""

import json
import random
import sys

from backend.app import Preferences

rng = random.Random(20261122)
BOOLS = [True, False, 0, 1, "yes", "no", "on", "2", None, 0.5]
TIMES = ["07:00", "00:00", "23:45", "24:00", "7:00", "07:10", "x07:00y", "25:00", "", None, 700]
DAYS = [[0], [0, 2, 4], [6, 1], [0, 0], [7], [], ["1"], [True], [1.0], None]
TONES = ["chime", "soft", "bright", "low", "glass", "spotify", "loud", None]
SPOTIFY = [None, "", "https://open.spotify.com/track/abc123", "http://open.spotify.com/track/a", 5]


def alarm() -> object:
    if rng.random() < 0.04:
        return rng.choice([None, "alarm", [], {"id": "a"}])
    item = {"id": rng.choice(["a1", "", "x" * 81]) if rng.random() < 0.08 else "a1",
            "name": rng.choice(["Wake", "", "x" * 81]) if rng.random() < 0.08 else "Wake",
            "time": rng.choice(TIMES) if rng.random() < 0.15 else "07:00",
            "days": rng.choice(DAYS) if rng.random() < 0.15 else [0, 2]}  # fmt: skip
    for name, pool in (("enabled", BOOLS), ("sound", TONES), ("spotify_url", SPOTIFY), ("extra", [1])):
        if rng.random() < 0.25:
            item[name] = rng.choice(pool)
    return item


def window(kind: str) -> object:
    if rng.random() < 0.04:
        return rng.choice([None, "w", []])
    start = rng.choice(TIMES[:6]) if rng.random() < 0.12 else rng.choice(["09:00", "16:00", "20:30"])
    item: dict = {"days": rng.choice(DAYS) if rng.random() < 0.12 else [rng.randint(0, 6)], "start": start}
    if kind == "work":
        item["end"] = rng.choice(TIMES) if rng.random() < 0.12 else rng.choice(["10:00", "18:00", "24:00"])
        if rng.random() < 0.3:
            item["subject"] = rng.choice(["Math", "  Math  ", "", "   ", None, "x" * 41])
    else:
        durations = [15, 30, 60, 90] if rng.random() < 0.7 else [0, -15, 20, 7140, 7155, "60", None]
        item["duration_min"] = rng.choice(durations)
        if kind == "protected":
            item["kind"] = rng.choice(["downtime", "commute", "meal", "nap"])
            if rng.random() < 0.4:
                titles = ["Piano", "  Piano ", "", "   ", None, "x" * 41, " " + "x" * 40, 7]
                item["title"] = rng.choice(titles)
        elif rng.random() < 0.3:
            item["subject"] = rng.choice(["Math", "  Math  ", "", "   ", None])
    if rng.random() < 0.05:
        item["extra"] = 1
    return item


SCALAR = {
    "reminders_enabled": BOOLS, "reminder_lead_min": [0, 5, 120, 121, -1, "5", 5.0, 5.5, True, None],
    "reminder_sound": BOOLS, "reminder_dnd_override": BOOLS,
    "timer_work_min": [1, 15, 30, 45, 180, 181, 0, "30"], "timer_break_min": [1, 15, 60, 61, 0, 10],
    "timer_long_break_min": [1, 30, 120, 121, 20], "timer_long_break_every": [2, 4, 12, 1, 13],
    "auto_split_pomodoro": BOOLS, "default_spotify_url": SPOTIFY,
    "day_cutoff": [None, "00:15", "23:45", "00:00", "23:50", "24:00", "9:00", "x", 5],
    "weekend_homework_free": BOOLS, "buffer_min": [0, 15, 30, 10, "15", 15.0, True, None],
    "urgent_first": BOOLS, "split_long_tasks": BOOLS, "show_weekends": BOOLS,
    "alert_volume": [0, 80, 100, 101, -1, "80"], "end_chime": BOOLS, "tray_notifications": BOOLS,
    "start_at_login": BOOLS, "preferred_view": ["week", "day", "month", "myday", "year", None],
    "sidebar_collapsed": BOOLS, "sidebar_width_px": [None, 200, 640, 199, 641, "300"],
    "theme_pack": ["system", "light-frost", "dark-frost", "nocturne", "slate", "pink"],
    "accent": ["default", "sky", "gold", "sea", "sand", "red"], "accent_chips": BOOLS,
    "motion": [None, "off", "normal", "extra", "reduce", "fast"], "alarm_tone": TONES,
    "planning_style": ["auto", "suggest", "manual", "never"], "drag_step_min": [5, 15, 10, "5", True],
    "clock_24h": BOOLS, "focus_audio": ["off", "rain", "lo-fi", "white-noise", "spotify", "jazz"],
    "focus_auto_mute": BOOLS, "focus_auto_complete": BOOLS, "unknown_extra": [1],
}


# Values pydantic accepts for each field: most picks come from here, so the writing rules are reached.
BAD = (None, "2", 0.5, "loud", "x", 5, 101, -1, 121, 181, 61, 13, 1)
GOOD = {name: [value for value in pool if value not in BAD] for name, pool in SCALAR.items()}
GOOD.update(
    timer_work_min=[15, 30, 45], timer_break_min=[15, 10], timer_long_break_min=[30, 20],
    timer_long_break_every=[2, 4, 12], reminder_lead_min=[0, 5, 120, "5", 5.0, True],
    day_cutoff=[None, "00:15", "23:45"], buffer_min=[0, 15, 30, 15.0, True], alert_volume=[0, 80, 100, "80"],
    sidebar_width_px=[None, 200, 640, "300"], drag_step_min=[5, 15, "5"][:2], unknown_extra=[],
)


def setup() -> object:
    if rng.random() < 0.1:
        return rng.choice([None, 3, {"version": 1, "extra": 1}])
    item: dict = {"version": rng.choice([1, 2, 100, 0, 101, "2"])}
    if rng.random() < 0.5:
        item["step"] = rng.choice([0, 3, 20, 21, -1])
    if rng.random() < 0.5:
        item["finished_at"] = rng.choice([None, "2026-11-05T19:00", "2026-11-05T19:00:30", "2026-11-05",
                                          "2026-11-05T19:00Z", "x" * 33])  # fmt: skip
    return item


def case() -> dict:
    prefs: dict = {"theme": rng.choice(["system", "slate", "nocturne"])}
    if rng.random() < 0.05:
        prefs["theme"] = rng.choice(["dark", None, 1])
    if rng.random() < 0.03:
        prefs.pop("theme")
    rate = 0.05 if rng.random() < 0.6 else 0.2
    for name, pool in SCALAR.items():
        if rng.random() < rate:
            good = GOOD.get(name) or pool
            prefs[name] = rng.choice(good) if rng.random() < 0.8 else rng.choice(pool)
    if rng.random() < 0.2:
        prefs["alarms"] = [alarm() for _ in range(rng.choice([0, 1, 1, 2, 21]))]
    if rng.random() < 0.25:
        prefs["protected"] = [window("protected") for _ in range(rng.choice([0, 1, 2, 3]))]
    if rng.random() < 0.25:
        prefs["work_windows"] = [window("work") for _ in range(rng.choice([0, 1, 2]))]
    if rng.random() < 0.15:
        prefs["study_windows"] = rng.choice([None, []]) if rng.random() < 0.2 else [window("study")]
    if rng.random() < 0.15:
        prefs["setup"] = setup()
    if rng.random() < 0.1:  # the split and pack rules
        prefs.update(auto_split_pomodoro=True, timer_work_min=rng.choice([30, 25]), timer_break_min=15)
    if rng.random() < 0.08:
        pack = rng.choice(["light-frost", "dark-frost"])
        prefs.update(theme_pack=pack, theme=rng.choice(["slate", "nocturne"]))
    return prefs


cases = []
seen = set()
# Fixed cases for rules the random ones can miss: pydantic searches an alarm's time for HH:MM anywhere.
for time in ["07:00", "x07:00y", "07:00x", "107:00", "7:00", "24:00"]:
    fixed = {"theme": "system", "alarms": [{"id": "a1", "name": "Wake", "time": time, "days": [2, 0]}]}
    seen.add(json.dumps(fixed, sort_keys=True))
    try:
        cases.append({"input": fixed, "written": Preferences.model_validate(fixed).model_dump()})
    except Exception:
        cases.append({"input": fixed, "written": None})
while len(cases) < int(sys.argv[2]):
    prefs = case()
    key = json.dumps(prefs, sort_keys=True)
    if key in seen:
        continue
    seen.add(key)
    try:
        cases.append({"input": prefs, "written": Preferences.model_validate(prefs).model_dump()})
    except Exception:
        cases.append({"input": prefs, "written": None})
with open(sys.argv[1], "w") as out:
    json.dump(cases, out, ensure_ascii=False, separators=(",", ":"))
accepted = sum(1 for c in cases if c["written"] is not None)
print(f"{len(cases)} cases, {accepted} accepted, {len(cases) - accepted} refused")
