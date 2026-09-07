# FlexWeek

Constraint scheduler for a student week. Places homework around school and sports, then explains why something moved.

Congressional App Challenge 2026. Python solver, HTML/CSS/JS UI. No accounts. No chatbot.

## Run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
uvicorn backend.app:app --reload
```

Open http://127.0.0.1:8000

## Phases

Work the checklist in [PHASES.md](PHASES.md). You are in **Phase 1** until the week grid shows both demo students and slot tests pass.

| Phase | Dates | Goal |
|---|---|---|
| 1 Skeleton | Sep 6–12 | Models, demos, grid |
| 2 Solver | Sep 13–19 | CSP v1 |
| 3 App | Sep 20–26 | Add/edit + Solve |
| 4 Must-ship | Sep 27–Oct 3 | Priority, energy, why |
| 5 Cascade | Oct 4–10 | Miss → reshuffle |
| 6 Contest | Oct 11–17 | Freeze, README, deploy |
| 7 Submit | Oct 18–25 | Video + CAC form |

Submit by Sunday, October 25, 2026, 8:00 p.m. PDT.
