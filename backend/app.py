"""FlexWeek FastAPI app — thin JSON door + static frontend.

Week 1: serve demos and UI only. No solver endpoint.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "data"
FRONTEND_DIR = ROOT / "frontend"

app = FastAPI(title="FlexWeek", version="0.1.0")


def _load_demo(name: str) -> dict:
    path = DATA_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(name)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/demos")
def get_demos() -> dict:
    """Return both seed demos (alex + jordan)."""
    return {
        "alex": _load_demo("demo_alex"),
        "jordan": _load_demo("demo_jordan"),
    }


@app.get("/api/demos/{name}")
def get_demo(name: str) -> dict:
    """Return a single demo by short name (alex | jordan)."""
    key = name if name.startswith("demo_") else f"demo_{name}"
    short = key.removeprefix("demo_")
    try:
        return _load_demo(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown demo: {short}") from None


@app.get("/api/solve")
@app.post("/api/solve")
def solve_stub() -> dict:
    """Week 1: solver not implemented."""
    raise HTTPException(status_code=501, detail="Solver not implemented in Week 1")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
