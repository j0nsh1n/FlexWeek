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

Phase 3 is complete. The [revised roadmap](roadmap.md) plans account-based app
and web delivery, Daily Scheduler interactions and dark mode. Accounts and
installed-app delivery are planned; the current runnable version still uses
browser storage and sample weeks.

Submit by Sunday, October 25, 2026, 8:00 p.m. PDT.
