# Wordle
A Wordle solver. Type your guesses, set the colors Wordle gave you, and it lists every word still possible, how likely
each one is to be the answer, and how well each one would split the rest if you guessed it next. It runs at
[engineerfamily.net/wordle/](https://engineerfamily.net/wordle/).

- **Probability**: the word's frequency in English ([wordfreq](https://pypi.org/project/wordfreq/)), normalized over the
  words still possible.
- **E(|v|)**: if you guess the word, the expected number of words left (the mean size of the non-empty groups its
  color patterns split the remaining words into). Lower is better.
- **Weighted E(|v|)**: the same, with each word counted by its zipf frequency, so common words weigh more.

Word list: <https://gist.github.com/dracos/dd0668f281e685bad51479e5acaadb93>.

## Run locally
```sh
pip install -r requirements.txt
uvicorn web.app:app
```
Then open <http://localhost:8000/wordle/>. Every route lives under `/wordle` (`WORDLE_BASE_PATH` changes it).
Above `WORDLE_EV_CAP` remaining words (default 3000) the E columns are skipped to keep requests fast.

## Docker
```sh
docker build -t wordle .
docker run -p 8000:8000 wordle
```

## CLI
`python run.py` (type `q` to quit).

## Development
- Tests: `pip install -r requirements.txt pytest httpx`, then `python -m pytest -q`.
- The opening table (`data/opening.csv`, every word against the full list) is precomputed:
  rerun `python scripts/precompute.py` after changing the word list or the solver.
