# AGENTS.md (auto-loaded through CLAUDE.md; keep it short)

Wordle: a Wordle solver. Given guesses and their colors, it lists the words still possible, how likely each one is
(word frequency) and how well each one splits the rest (expected remaining size, E(|v|), plain and frequency-weighted).

## Map
- `solver.py`: the fast core (numpy). Pattern codes are base 3 per position: 0 black, 1 yellow, 2 green (0–242).
  `pattern`, `pattern_matrix`, `filter_candidates`, `probabilities`, `expected_sizes`, `solve`.
- `predictor.py`: the `Predictor` class the CLI uses; it delegates to `solver.py`.
- `run.py`: interactive CLI.
- `web/`: FastAPI app (`app.py`, routes under `/wordle`) and the page (`static/index.html`, `static/app.js`, no build step).
- `data/opening.csv`: the no-guess table, from `scripts/precompute.py` (rerun after changing the word list or solver).
- `Dockerfile`: the image engineerfamily deploys (`uvicorn` on port 8000).
- `input/valid-wordle-words.txt`: the word list. `output/expected-valid-size.csv`: E(|v|) of every word against the full
  list (a regression fixture for the tests).
- `agents/runner.toml`: how the shared agent-runner sees this repo (validate commands, risk gate, `[release]`: every merged PR
  gets the next `vX.Y.Z` tag, which engineerfamily's `components.toml` pins).
- `tests/`: pytest. `test.ipynb`: experiments, kept as is.

## Run
- CLI: `python run.py` (type `q` to quit).
- Web: `uvicorn web.app:app`, then `http://localhost:8000/wordle/`.
- Tests: `pip install -r requirements.txt pytest httpx`, then `python -m pytest -q`. CI runs them on every PR (job `test`)
  and builds and health-checks the image (job `docker`).

## Rules
- Python 3.12; `requirements.txt` holds pinned runtime dependencies only.
- Deployed by the engineerfamily repo (served at `/wordle/`); a merge here deploys nothing by itself.
- Public repo: never commit secrets or `.env` files. Work on a branch and open a PR to `main`.
