import csv
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import solver  # noqa: E402
from web import app as web_app  # noqa: E402

client = TestClient(web_app.app)
N_WORDS = len(solver.WORDS)


def post(rows):
    return client.post("/wordle/api/solve", json={"rows": rows})


def test_health():
    r = client.get("/wordle/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "words": N_WORDS}


def test_index_and_redirect():
    r = client.get("/wordle/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert 'id="grid"' in r.text
    r = client.get("/wordle", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/wordle/"
    assert client.get("/wordle/static/app.js").status_code == 200


def test_words():
    r = client.get("/wordle/api/words")
    assert r.status_code == 200
    assert len(r.json()) == N_WORDS
    assert "max-age=86400" in r.headers["cache-control"]


def test_no_rows_is_the_opening_table():
    body = post([]).json()
    assert body["remaining"] == N_WORDS
    assert len(body["words"]) == N_WORDS
    assert body["capped"] is False


def test_one_row_keeps_the_solution():
    code = solver.pattern_string(solver.pattern("crane", "abide"))
    body = post([{"guess": "CRANE", "pattern": code}]).json()
    words = [w["word"] for w in body["words"]]
    assert "abide" in words
    assert body["remaining"] == len(words)
    assert sum(w["probability"] for w in body["words"]) == pytest.approx(1)
    probs = [w["probability"] for w in body["words"]]
    assert probs == sorted(probs, reverse=True)
    assert all(w["ev"] is not None and w["wev"] is not None for w in body["words"])


def test_no_match():
    body = post([{"guess": "crane", "pattern": "ggggg"}, {"guess": "crane", "pattern": "bbbbb"}]).json()
    assert body == {"remaining": 0, "capped": False, "cap": web_app.EV_CAP, "words": []}


@pytest.mark.parametrize("rows, message", [
    ([{"guess": "xxxxx", "pattern": "bbbbb"}], "Row 1: 'xxxxx' is not in the word list"),
    ([{"guess": "crane", "pattern": "bbbbb"}, {"guess": "crane", "pattern": "bbbbx"}], "Row 2:"),
    ([{"guess": "crane", "pattern": "bbbbb"}] * 7, "At most 6 rows"),
])
def test_bad_input(rows, message):
    r = post(rows)
    assert r.status_code == 422
    assert r.json()["detail"].startswith(message)


def test_capped(monkeypatch):
    monkeypatch.setattr(web_app, "EV_CAP", 10)
    body = post([{"guess": "crane", "pattern": "bbbbb"}]).json()
    assert body["capped"] is True
    assert body["cap"] == 10
    assert body["remaining"] > 10
    assert all(w["ev"] is None and w["wev"] is None for w in body["words"])


def test_opening_csv_matches_solver():
    with (ROOT / "data/opening.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))[:3]
    words = [r["word"] for r in rows]
    ev = solver.expected_sizes(words, solver.WORDS)
    wev = solver.expected_sizes(words, solver.WORDS, weighted=True)
    for r, e, w in zip(rows, ev, wev):
        assert float(r["ev"]) == pytest.approx(e, abs=1e-6)
        assert float(r["wev"]) == pytest.approx(w, abs=1e-6)
