"""
Web app for the solver: the tile-grid page and a small JSON API, all under BASE (default /wordle,
because nginx proxies /wordle/ here without stripping the prefix).
"""
import csv
import os
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import solver

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
BASE = os.environ.get("WORDLE_BASE_PATH", "/wordle").rstrip("/")
EV_CAP = int(os.environ.get("WORDLE_EV_CAP", "3000"))


#opening table (no rows), precomputed by scripts/precompute.py
def load_opening():
    with (ROOT / "data/opening.csv").open(newline="") as f:
        return [
            {"word": r["word"], "probability": float(r["probability"]), "ev": float(r["ev"]), "wev": float(r["wev"])}
            for r in csv.DictReader(f)
        ]


WORD_LIST = [str(w) for w in solver.WORDS]
WORD_SET = frozenset(WORD_LIST)
OPENING = load_opening()
#warm the frequency caches so the first request doesn't pay for them
solver.probabilities(solver.WORDS)
solver.expected_sizes(solver.WORDS[:1], solver.WORDS, weighted=True)


class Row(BaseModel):
    guess: str
    pattern: str


class SolveRequest(BaseModel):
    rows: list[Row] = Field(default_factory=list)


app = FastAPI(title="Wordle solver", docs_url=None, redoc_url=None, openapi_url=None)
#the opening table is ~900 KB of JSON
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get(BASE, include_in_schema=False)
def base_redirect():
    return RedirectResponse(f"{BASE}/", status_code=307)


@app.get(f"{BASE}/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get(f"{BASE}/api/health")
def health():
    return {"ok": True, "words": len(WORD_LIST)}


@app.get(f"{BASE}/api/words")
def words():
    return JSONResponse(WORD_LIST, headers={"Cache-Control": "public, max-age=86400"})


@app.post(f"{BASE}/api/solve")
def solve(req: SolveRequest):
    if len(req.rows) > 6:
        raise HTTPException(422, f"At most 6 rows, got {len(req.rows)}")
    rows = []
    for i, row in enumerate(req.rows, start=1):
        guess = row.guess.strip().lower()
        if guess not in WORD_SET:
            raise HTTPException(422, f"Row {i}: {row.guess!r} is not in the word list")
        try:
            solver.parse_pattern(row.pattern.strip().lower())
        except ValueError:
            raise HTTPException(422, f"Row {i}: {row.pattern!r} is not a valid pattern (5 of b, y, g)")
        rows.append((guess, row.pattern.strip().lower()))

    if not rows:
        return {"remaining": len(OPENING), "capped": False, "cap": EV_CAP, "words": OPENING}

    candidates = solver.filter_candidates(rows)
    if len(candidates) > EV_CAP:
        probs = solver.probabilities(candidates)
        out = [
            {"word": str(candidates[i]), "probability": float(probs[i]), "ev": None, "wev": None}
            for i in np.argsort(-probs, kind="stable")
        ]
        return {"remaining": len(out), "capped": True, "cap": EV_CAP, "words": out}
    out = solver.solve(rows) if len(candidates) else []
    return {"remaining": len(out), "capped": False, "cap": EV_CAP, "words": out}

app.mount(f"{BASE}/static", StaticFiles(directory=STATIC), name="static")
