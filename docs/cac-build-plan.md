# Contest build plan (original, 2026-09-06)

Working title was Reslot. The public name is FlexWeek.

This file is the day-one contest brief. The living schedule is `roadmap.md`.
The product contract is `spec.md`. Several locks below were later reversed
with owner approval: accounts, SQLite, a desktop installer, and Daily
Scheduler interactions shipped. Keep this file as the original brief.
If a "Killed now" or "Never" line here disagrees with `spec.md` or
`roadmap.md`, those files win.

---

# Reslot — Congressional App Challenge 2026 build plan

Student constraint scheduler. You code. Partner tests, copy, and film.
Deadline: **Monday, October 26, 2026, 9:00 a.m. PDT**. Submit by **Sunday, October 25, 8:00 p.m. PDT**.

Do **not** fork or submit [Local-Schedule-Assistant](https://github.com/j0nsh1n/Local-Schedule-Assistant). That is a desktop LLM calendar. This is a new student web app.

---

## Product lock

**One loop:** enter school/sports/sleep as locked blocks + homework as flexible tasks → solver places the week → every conflict shows a plain-English why → miss a block and the rest of the week reshuffles with reasons.

**Must ship (feature freeze Oct 3):**

1. CSP / backtracking solver on 15-minute slots
2. Priority weighting (test > quiz > homework > reading)
3. Energy windows (morning / afternoon / evening: high / medium / low)
4. Explainable conflict log
5. Week calendar UI, local demo data, no accounts

**Week 5 only if must-ship is green:**

6. Auto-reschedule cascade
7. Deadline slack / “in danger” badges

**Stretch (only if week 5 done by Oct 10):** grade-impact overlay as a priority input. Not a second app.

**Killed now:** LLM chat, Google Calendar OAuth, accounts, native iOS/Android, Electron/.exe, time-estimation learning, shared/team CRDT, payments, live AI as the product, Java/Swift/C++/Kotlin/PHP/Ruby.

---

## Languages

Ship **four**. List at most **two** extras, and only if they do real work.

| Language | Role | Required |
|---|---|---|
| Python 3.14 | Solver, pytest, FastAPI `/api/solve` | Yes |
| JavaScript | Calendar UI, forms, fetch, localStorage | Yes |
| HTML5 | Page structure, week grid markup | Yes |
| CSS | Desktop week grid + phone layout | Yes |
| TypeScript | Optional typed UI if JS gets messy after week 3 | No |
| SQL | Optional SQLite if JSON files get painful | No |

Do not add a fifth language for the writeup. Judges will open GitHub.

Python owns the engine (you already think in it; tests stay fast). The browser owns the page. FastAPI is a thin JSON door, not a second product.

---

## Devices

| Target | Priority | Done means |
|---|---|---|
| Laptop / desktop browser (Chrome, Edge, Firefox, Safari) | Primary | Full week grid, Solve, explain panel. Film here. Design at 1280px. |
| Phone / tablet browser | Secondary | Load demo, add a task, run Solve. Grid may scroll. Usable at 390px. |
| Installed PWA | Optional, week 6 only | Add to Home Screen if leftover time. |
| Native App Store / Play | Never | Will eat the contest. |
| Desktop installer | Never | Do not ship a second Python GUI. |

One public URL is the whole distribution plan (Render, same stack you already use). Test Safari on an iPhone once in week 6.

---

## Repo layout

```
reslot/
  README.md
  ARCHITECTURE.md
  backend/
    app.py              # FastAPI: static + /api/solve
    solver.py           # CSP, no FastAPI imports
    models.py           # dataclasses / pydantic
    explain.py          # reason codes → strings
    data/demo_alex.json
    data/demo_jordan.json
    tests/test_solver.py
  frontend/
    index.html
    styles.css
    app.js
  requirements.txt
```

Solver has **zero** knowledge of HTTP. `app.py` only validates JSON and calls `solve()`. Frontend never reimplements placement.

### Data model

```python
from dataclasses import dataclass, field
from typing import Literal

BlockKind = Literal["locked", "flexible"]
Priority = Literal[1, 2, 3, 4]  # 1 = test, 4 = reading
Energy = Literal["high", "medium", "low"]

@dataclass
class TimeBlock:
    id: str
    title: str
    kind: BlockKind
    duration_min: int          # multiple of 15
    days: list[int]            # 0–6
    priority: Priority
    energy: Energy
    earliest: str | None = None
    latest: str | None = None  # deadline for flexible
    start: str | None = None    # locked start, or solver fill
    course: str | None = None

@dataclass
class Move:
    block_id: str
    reason: str
    from_start: str | None = None
    to_start: str | None = None

@dataclass
class SolveTrace:
    placed: list[TimeBlock]
    unplaced: list[TimeBlock]
    moves: list[Move]
    failed_constraints: list[str]
    solve_ms: float
    complete: bool
```

Times are naive local `YYYY-MM-DDTHH:mm`. Assume America/Los_Angeles. No timezone math in v1.

### Solver (efficient)

- Discretize Mon–Sun 6:00–23:00 into 15-min slots (68/day × 7 = 476).
- Variables = flexible tasks. Domain = legal start slots.
- MRV, then highest priority, then earliest deadline.
- LCV + energy match for value order.
- Forward checking after each placement.
- Hard cap: **150 ms**. On timeout, best partial + unplaced reasons. Never block the event loop (run solve in a thread or keep it pure-CPU and short).
- Cascade (week 5): missed block → locked-unavailable → re-solve remaining flexible → diff → move list.

Reason codes (partner writes English; you keep the enum):

- `LOCKED_OVERLAP`
- `DEADLINE_MISS`
- `NO_SLOT_LEFT`
- `PRIORITY_PREEMPT`
- `ENERGY_MISMATCH` (soft)
- `SLEEP_GUARD`
- `RESHUFFLE_AFTER_MISS`

---

## Calendar (today = Sun Sep 6 → submit Sun Oct 25)

| Week | Dates | You ship | Partner ships | Exit test |
|---|---|---|---|---|
| 1 | Sep 6–12 | Repo, models, seed JSON, HTML week grid, FastAPI serves static | 2 real weekly calendars, 8 tasks each, no real names | `pytest` runs; grid renders seed |
| 2 | Sep 13–19 | `solver.py` v1: locked + flexible, no priority | Break it: overlapping sports, 6-hour homework night | 20 fixture tests green; debug panel dumps a week |
| 3 | Sep 20–26 | Add/edit/delete in JS, lock vs flexible, POST `/api/solve` | Click every control; 10-row bug list | New user can build a week without you |
| 4 | Sep 27–Oct 3 | Priority, energy, explain panel | Plain-English strings per reason code; 5 classmates try it | **Must-ship freeze.** Demo script v1 on paper |
| 5 | Oct 4–10 | Cascade + slack badges **or** polish if tests are red | Miss a block on purpose; note “felt wrong” cases | Video beat: miss → ripple → reasons |
| 6 | Oct 11–17 | **Hard feature freeze Oct 11.** A11y, README, public Render URL | Video script, voiceover practice | Deployed URL + README a judge can follow |
| 7 | Oct 18–25 | Bugfixes only, 90-second film, CAC form | Film, edit, cue cards | Submitted **Oct 25 evening** |

If week 4 exit fails, skip week 5 features.

---

## Week-by-week detail

### Week 1 — Sep 6–12: skeleton

**You**

- Public repo `reslot`. Python 3.14, FastAPI, pytest.
- `models.py` + slot helpers. No solver yet.
- Seed `demo_alex.json`, `demo_jordan.json` from partner data.
- `index.html` + `styles.css`: 7-column grid 6:00–23:00, locked blocks painted, flexible list in a sidebar.
- `app.py` serves `frontend/` and `GET /api/demos`.
- README stub: problem, languages, how to run (`uvicorn`, open localhost).

**Partner**

- Interview 3 students. Capture wake, school, sport, commute, sleep, 6–10 assignments with durations and deadlines.
- Anonymize names. Mark immovable blocks.
- One-sentence pitch: “It places your homework around school and sports, then tells you why something moved.”

**Debug / efficiency**

- Slot math unit tests. Duration must be a multiple of 15.
- One `overlaps(a, b)`. No duplicate date helpers.
- Ban solver logic in `app.js` this week.

**Exit:** `uvicorn` shows two demo weeks. `pytest` has ≥10 helper tests.

### Week 2 — Sep 13–19: solver v1

**You**

- `solve(blocks) -> SolveTrace` with backtracking + MRV + forward checking.
- Locked intervals + deadlines. Sleep 23:00–6:00 is a locked guard unless partner data says otherwise.
- Debug panel in JS: `solve_ms`, placed count, unplaced titles.
- Fixtures: empty, packed, impossible, one 3-hour paper due tomorrow.

**Partner**

- Three “break it” cases on paper, then in the app.
- Expected vs actual in a shared doc.

**Debug / efficiency**

- Packed fixture must stay under 150 ms or add heuristics before features.
- Clone domains per recursion level.
- Property: no output overlaps; no flexible block starts after its deadline.
- Solver stays sync and pure so pytest is the source of truth.

**Exit:** Packed fixture solves or fails with `NO_SLOT_LEFT`, never hangs.

### Week 3 — Sep 20–26: usable app

**You**

- HTML forms: add locked, add flexible.
- Persist last week in `localStorage` (JS). Demos stay as Python JSON files.
- Solve button → `POST /api/solve` → paint trace.
- Skip drag-and-drop if it costs more than a day.

**Partner**

- Build a week from scratch. Every confusion is a bug.
- 8 realistic assignments from syllabi (no copyrighted PDFs in the repo).

**Debug**

- Validate `duration_min % 15 === 0` in the form **and** in Pydantic.
- If localStorage is corrupt, reset to a demo instead of crashing.
- CORS is not a problem if FastAPI serves the frontend. Do not split origins.

**Exit:** Partner can create, solve, refresh, and still see the week.

### Week 4 — Sep 27–Oct 3: must-ship complete

**You**

- Priority + energy on the model and in search order.
- Explain panel: moves + failed constraints using partner copy.
- Click a move → highlight that block.
- Test: last good slot, test vs reading → reading unplaced, `PRIORITY_PREEMPT`.

**Partner**

- User-facing sentence for each reason code.
- 5 classmates, 10 minutes, you not in the room. Keep 3 quotes for CAC.

**Freeze Oct 3:** no new feature types.

**Exit:** Storyboard: load demo → solve → click unplaced → read the why.

### Week 5 — Oct 4–10: cascade + slack (or polish)

**Go / no-go Monday Oct 4:** if week 4 is red, polish only.

**If go:** “I missed this block” → re-solve → list diffs. Slack hours + ok/tight/danger badges. Sleep never stolen.

**Partner:** time the 90-second demo around the miss-and-ripple.

### Week 6 — Oct 11–17: contest surface

**Hard freeze Sunday Oct 11 6:00 p.m.**

**You:** keyboard, contrast, reduced-motion, empty states, Render deploy, GPL-3.0 license, both names on README. Disclose AI if you used a copilot.

**Partner:** final script + B-roll.

Optional this week only: `manifest.json` PWA, or SQLite instead of JSON. Neither is required.

### Week 7 — Oct 18–25: ship

Bugs only. Film. CAC form. Submit Oct 25 evening.

---

## Roles

| You | Partner |
|---|---|
| Python solver, FastAPI, HTML/CSS/JS, tests, GitHub, Render | Real calendars, copy, usability, video |
| 150 ms cap, fixtures | “Felt wrong” log |
| CAC technical writeup | Inspiration / learned / improve answers |

If a judge asks who coded it, the answer is you. Partner work is research, QA, and communication.

---

## Demo video (90–120 seconds)

1. Names, school, “Reslot — a constraint solver for a student week.”
2. School + sport + three deadlines.
3. Load demo → Solve.
4. Click unplaced/moved → read the why.
5. Miss practice → cascade → slack.
6. “Python solver, HTML/JS UI, runs in the browser with a local API, no account.”
7. GitHub URL.

No music under the explanation. No AI voice.

---

## Test matrix

| ID | Case | Expect |
|---|---|---|
| T1 | Only locked school | Identity schedule, 0 moves |
| T2 | One homework, plenty of room | Placed, energy-matched if possible |
| T3 | Test vs reading, one slot | Test placed, reading unplaced, `PRIORITY_PREEMPT` |
| T4 | 6h homework, 2h free | Unplaced remainder, `NO_SLOT_LEFT` |
| T5 | Deadline before school ends | Unplaced, `DEADLINE_MISS` |
| T6 | Sport overlaps homework | Homework domain excludes sport |
| T7 | Packed fixture | `solve_ms < 150` |
| T8 | Corrupt storage | Reset to demo |
| T9 | Miss locked sport (wk5) | Downstream flexible moves; sleep intact |
| T10 | Slack danger (wk5) | 0 float → danger |

Run T1–T8 on every change after week 2.

---

## CAC form (draft)

- **Inspiration:** Students plan by guilt, not constraints. Two real weeks from our school broke every to-do list.
- **Challenges:** Search space, explanation quality, 150 ms budget, keeping Python and JS from duplicating logic.
- **Learned:** Heuristics beat extra features; users need the why more than a prettier calendar.
- **Improve:** Grade-weighted priorities, ICS import (not OAuth), better duration estimates.
- **Languages:** Python, JavaScript, HTML5, CSS.
- **AI:** Disclose Copilot/ChatGPT. The solver is handwritten.

Registration: personal email, not school. One teammate creates the profile and invites the other. One district only.

---

## Kill list if a week slips

| Behind after | Cut |
|---|---|
| Week 2 | Energy (keep priority only) |
| Week 3 | Drag-and-drop forever |
| Week 4 | Week 5 cascade + slack |
| Week 5 | Grade-impact, TypeScript rewrite, SQL |
| Week 6 | All code except crash fixes |

---

## This week (Sep 6–12) checklist

- [x] Language lock: Python, JavaScript, HTML5, CSS
- [x] Device lock: desktop web first, phone browser second, no native
- [ ] Name the app (working title: Reslot)
- [ ] New public GitHub repo
- [ ] FastAPI + `frontend/` skeleton
- [ ] Partner: two anonymized weeks in a spreadsheet tonight or tomorrow
- [ ] You: models + week grid by Friday Sep 11
- [ ] Register for CAC this week
- [ ] Confirm congressional district and that the Member is hosting
