from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.models import TimeBlock, WeekRequest
from backend.solver import solve

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
DATA = Path(__file__).resolve().parent / "data"

app = FastAPI(title="FlexWeek")


def _load_demo(name: str) -> list[TimeBlock]:
    path = DATA / f"demo_{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="unknown demo")
    raw = json.loads(path.read_text())
    return [TimeBlock.model_validate(item) for item in raw]


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/demos/{name}")
def get_demo(name: str) -> dict:
    if name not in {"alex", "jordan"}:
        raise HTTPException(status_code=404, detail="unknown demo")
    blocks = _load_demo(name)
    return {"name": name, "blocks": [block.model_dump() for block in blocks]}


@app.post("/api/solve")
def post_solve(week: WeekRequest) -> dict:
    trace = solve(week.blocks)
    return trace.model_dump()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
