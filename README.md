# FlexWeek

**FlexWeek** places homework around school and sports, then tells you why something moved.

Congressional App Challenge 2026 student project (constraint scheduler for a student week). Working title was *Reslot*; the public name is **FlexWeek**.

## Languages

Python · JavaScript · HTML5 · CSS only.

## What Week 1 includes

- Data models (`TimeBlock`, `Move`, `SolveTrace`) and 15-minute slot helpers
- Two anonymized demo weeks (Alex, Jordan)
- FastAPI app that serves the frontend and `GET /api/demos`
- A 7-column week grid UI that paints **locked** blocks and lists **flexible** tasks

No solver yet — placement/engine logic lands in a later week.

## Run locally

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app:app --reload
```

Open http://127.0.0.1:8000/

## Tests

```bash
pytest -q
```

## API (Week 1)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/demos` | Both seed JSON demos |
| GET | `/api/demos/{name}` | `alex` or `jordan` |
| GET/POST | `/api/solve` | **501** stub — not implemented this week |

## Time model

Naive local timestamps `YYYY-MM-DDTHH:mm` in `America/Los_Angeles`. No timezone conversion math.

## License

GPL-3.0 — see [LICENSE](LICENSE).

Built for the [Congressional App Challenge](https://www.congressionalappchallenge.us/) 2026.
